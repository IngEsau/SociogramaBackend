# core/views/comite/helpers.py
"""
Batch helpers para el módulo Comité.

Reemplazan las llamadas N×_calcular_nodos_sociograma() y
N×_calcular_conexiones_sociograma() por versiones que hacen
queries fijas independientemente del número de grupos.

Uso:
    from core.views.comite.helpers import (
        _calcular_nodos_batch,
        _calcular_conexiones_batch,
    )
"""
from django.db.models import Count, Sum, Case, When, IntegerField

from core.models import AlumnoGrupo, Respuesta, CuestionarioEstado
from core.views.academic.cuestionarios import _clasificar_alumno


def _calcular_nodos_batch(cuestionario, grupos_list):
    """
    Versión batch de _calcular_nodos_sociograma.
    Calcula nodos de TODOS los grupos en ~6 queries fijas.

    Args:
        cuestionario: instancia de Cuestionario
        grupos_list:  list[Grupo] — grupos a procesar

    Retorna:
        dict { grupo_id: { 'nodos': [...], 'total_alumnos': N, 'respuestas_completas': N } }

    Queries ejecutadas:
        1. AlumnoGrupo — .values() evita instanciar objetos ORM para ~9k registros
        2. preguntas positivas del cuestionario
        3. preguntas negativas del cuestionario
        4. Respuesta — puntos recibidos por alumno (batch annotate)
        5. Respuesta — elecciones realizadas por alumno (batch)
        6. CuestionarioEstado — estados (batch)
    """
    grupos_ids = [g.id for g in grupos_list]

    # Query 1: todos los alumnos de todos los grupos
    # .values() en lugar de select_related — evita instanciar objetos ORM
    # para ~9,000 registros con 300 grupos activos
    alumnos_qs = AlumnoGrupo.objects.filter(
        grupo_id__in=grupos_ids,
        activo=True
    ).values(
        'grupo_id',
        'alumno_id',
        'alumno__matricula',
        'alumno__user__nombre_completo',
    )

    grupos_alumnos = {}   # grupo_id → list[dict]
    alumno_a_grupo = {}   # alumno_id → grupo_id

    for row in alumnos_qs:
        gid = row['grupo_id']
        aid = row['alumno_id']
        if gid not in grupos_alumnos:
            grupos_alumnos[gid] = []
        grupos_alumnos[gid].append(row)
        alumno_a_grupo[aid] = gid

    todos_alumnos_ids = list(alumno_a_grupo.keys())

    # Queries 2 y 3: preguntas por polaridad
    preguntas_positivas_ids = list(
        cuestionario.preguntas.filter(
            pregunta__tipo='SELECCION_ALUMNO',
            pregunta__polaridad='POSITIVA'
        ).values_list('pregunta_id', flat=True)
    )
    preguntas_negativas_ids = list(
        cuestionario.preguntas.filter(
            pregunta__tipo='SELECCION_ALUMNO',
            pregunta__polaridad='NEGATIVA'
        ).values_list('pregunta_id', flat=True)
    )
    todas_preguntas_ids = preguntas_positivas_ids + preguntas_negativas_ids

    # Query 4: puntos recibidos — batch para todos los alumnos
    puntos_qs = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id__in=todas_preguntas_ids,
        seleccionado_alumno_id__in=todos_alumnos_ids
    ).values('seleccionado_alumno_id').annotate(
        puntos_positivos=Sum(
            Case(
                When(pregunta_id__in=preguntas_positivas_ids, then='puntaje'),
                default=0,
                output_field=IntegerField()
            )
        ),
        puntos_negativos=Sum(
            Case(
                When(pregunta_id__in=preguntas_negativas_ids, then='puntaje'),
                default=0,
                output_field=IntegerField()
            )
        ),
        elecciones_recibidas=Count('id'),
    )
    puntos_map = {r['seleccionado_alumno_id']: r for r in puntos_qs}

    # Query 5: elecciones realizadas — batch
    realizadas_qs = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id__in=todas_preguntas_ids,
        alumno_id__in=todos_alumnos_ids,
        seleccionado_alumno__isnull=False
    ).values('alumno_id').annotate(total=Count('id'))
    realizadas_map = {r['alumno_id']: r['total'] for r in realizadas_qs}

    # Query 6: estados — batch
    estados_qs = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        alumno_id__in=todos_alumnos_ids,
        grupo_id__in=grupos_ids
    ).values('alumno_id', 'estado')
    estados_map = {r['alumno_id']: r['estado'] for r in estados_qs}

    # max_impacto por grupo en memoria
    max_impacto_por_grupo = {}
    for aid, gid in alumno_a_grupo.items():
        p = puntos_map.get(aid, {})
        impacto = (p.get('puntos_positivos') or 0) + (p.get('puntos_negativos') or 0)
        if gid not in max_impacto_por_grupo or impacto > max_impacto_por_grupo[gid]:
            max_impacto_por_grupo[gid] = impacto

    # Construir nodos por grupo en memoria
    resultado = {}
    for grupo in grupos_list:
        gid         = grupo.id
        rows        = grupos_alumnos.get(gid, [])
        max_impacto = max_impacto_por_grupo.get(gid, 0)
        nodos       = []
        respuestas_completas = 0

        for row in rows:
            aid    = row['alumno_id']
            p      = puntos_map.get(aid, {})

            puntos_positivos      = p.get('puntos_positivos') or 0
            puntos_negativos      = p.get('puntos_negativos') or 0
            impacto_total         = puntos_positivos + puntos_negativos
            elecciones_recibidas  = p.get('elecciones_recibidas') or 0
            elecciones_realizadas = realizadas_map.get(aid, 0)
            estado                = estados_map.get(aid, 'PENDIENTE')

            if estado == 'COMPLETADO':
                respuestas_completas += 1

            tipo = _clasificar_alumno(
                puntos_positivos, puntos_negativos, impacto_total, max_impacto
            )

            nodos.append({
                'alumno_id':              aid,
                'matricula':              row['alumno__matricula'],
                'nombre':                 row['alumno__user__nombre_completo'],
                'tipo':                   tipo,
                'puntos_positivos':       puntos_positivos,
                'puntos_negativos':       puntos_negativos,
                'impacto_total':          impacto_total,
                'tamano':                 impacto_total,
                'elecciones_recibidas':   elecciones_recibidas,
                'elecciones_realizadas':  elecciones_realizadas,
                'completo':               estado == 'COMPLETADO',
            })

        resultado[gid] = {
            'total_alumnos':        len(rows),
            'respuestas_completas': respuestas_completas,
            'nodos':                nodos,
        }

    return resultado


def _calcular_conexiones_batch(cuestionario, grupos_list):
    """
    Versión batch de _calcular_conexiones_sociograma.
    Calcula conexiones de TODOS los grupos en ~3 queries fijas.

    Args:
        cuestionario: instancia de Cuestionario
        grupos_list:  list[Grupo] — grupos a procesar

    Retorna:
        dict { grupo_id: [ conexion, ... ] }

    Queries ejecutadas:
        1. AlumnoGrupo — alumnos por grupo
        2. preguntas sociométricas del cuestionario
        3. Respuesta — .values() evita instanciar objetos ORM para todas las respuestas
    """
    grupos_ids = [g.id for g in grupos_list]

    # Query 1: alumnos por grupo
    alumnos_qs = AlumnoGrupo.objects.filter(
        grupo_id__in=grupos_ids,
        activo=True
    ).values('alumno_id', 'grupo_id')

    grupo_a_alumnos = {}   # grupo_id → set(alumno_id)
    alumno_a_grupo  = {}   # alumno_id → grupo_id

    for row in alumnos_qs:
        gid = row['grupo_id']
        aid = row['alumno_id']
        if gid not in grupo_a_alumnos:
            grupo_a_alumnos[gid] = set()
        grupo_a_alumnos[gid].add(aid)
        alumno_a_grupo[aid] = gid

    todos_alumnos_ids = list(alumno_a_grupo.keys())

    # Query 2: preguntas sociométricas con datos
    preguntas_socio = list(
        cuestionario.preguntas.filter(
            pregunta__tipo='SELECCION_ALUMNO'
        ).values(
            'pregunta_id',
            'pregunta__max_elecciones',
            'pregunta__polaridad',
        )
    )
    preguntas_ids = [p['pregunta_id'] for p in preguntas_socio]

    # Query 3: todas las respuestas de todos los grupos
    # .values() en lugar de select_related — evita instanciar objetos ORM
    respuestas_qs = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id__in=preguntas_ids,
        alumno_id__in=todos_alumnos_ids,
        seleccionado_alumno_id__in=todos_alumnos_ids
    ).values(
        'alumno_id',
        'seleccionado_alumno_id',
        'alumno__user__nombre_completo',
        'seleccionado_alumno__user__nombre_completo',
        'pregunta__polaridad',
        'puntaje',
    )

    # Agrupar conexiones por grupo en memoria
    conexiones_por_grupo = {}   # grupo_id → { (origen_id, destino_id): data }

    for resp in respuestas_qs:
        origen_id  = resp['alumno_id']
        destino_id = resp['seleccionado_alumno_id']
        gid        = alumno_a_grupo.get(origen_id)
        if gid is None:
            continue

        if gid not in conexiones_por_grupo:
            conexiones_por_grupo[gid] = {}

        key = (origen_id, destino_id)
        if key not in conexiones_por_grupo[gid]:
            conexiones_por_grupo[gid][key] = {
                'origen_id':      origen_id,
                'origen_nombre':  resp['alumno__user__nombre_completo'],
                'destino_id':     destino_id,
                'destino_nombre': resp['seleccionado_alumno__user__nombre_completo'],
                'peso_total':     0,
                'polaridad':      resp['pregunta__polaridad'],
            }
        conexiones_por_grupo[gid][key]['peso_total'] += resp['puntaje'] or 1

    # Construir resultado por grupo
    resultado = {}

    for grupo in grupos_list:
        gid               = grupo.id
        alumnos_ids_grupo = grupo_a_alumnos.get(gid, set())
        conexiones_dict   = conexiones_por_grupo.get(gid, {})

        total_puntos_posibles = sum(
            len(alumnos_ids_grupo) * p['pregunta__max_elecciones'] * p['pregunta__max_elecciones']
            for p in preguntas_socio
        )

        conexiones = []
        for key, data in conexiones_dict.items():
            origen_id, destino_id = key
            key_inversa   = (destino_id, origen_id)
            puntos_mutuos = data['peso_total']
            if key_inversa in conexiones_dict:
                puntos_mutuos += conexiones_dict[key_inversa]['peso_total']

            porcentaje_mutuo = (
                round(puntos_mutuos / total_puntos_posibles * 100, 2)
                if total_puntos_posibles > 0 else 0
            )

            conexiones.append({
                'origen_id':        data['origen_id'],
                'origen_nombre':    data['origen_nombre'],
                'destino_id':       data['destino_id'],
                'destino_nombre':   data['destino_nombre'],
                'peso':             data['peso_total'],
                'tipo_conexion':    'fuerte' if porcentaje_mutuo >= 33 else 'debil',
                'porcentaje_mutuo': porcentaje_mutuo,
                'es_mutua':         key_inversa in conexiones_dict,
                'polaridad':        data['polaridad'],
            })

        resultado[gid] = conexiones

    return resultado