# core/views/academic/cuestionarios.py
"""
Endpoints para Tutores - Gestión de Cuestionarios
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Avg, Sum, Case, When, IntegerField

from core.models import (
    Cuestionario, CuestionarioEstado, Grupo, Respuesta, Pregunta, Alumno,
    AlumnoGrupo
)
from core.serializers import (
    CuestionarioListSerializer,
    CuestionarioDetailSerializer,
)
from core.utils.decorators import require_tutor


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def listar_cuestionarios_tutor_view(request):
    """
    Lista cuestionarios del tutor: el activo si existe, si no el último que fue activado.
    GET /api/academic/cuestionarios/
    """
    periodos_tutor = Grupo.objects.filter(
        tutor=request.docente
    ).values_list('periodo_id', flat=True).distinct()

    # Primero buscar si hay uno activo
    cuestionarios = Cuestionario.objects.filter(
        periodo_id__in=periodos_tutor,
        activo=True
    ).select_related('periodo').order_by('-creado_en')

    # Si no hay activo, mostrar el último que fue activado (tiene CuestionarioEstado)
    if not cuestionarios.exists():
        ultimo_id = (
            CuestionarioEstado.objects
            .filter(
                cuestionario__periodo_id__in=periodos_tutor,
                grupo__tutor=request.docente
            )
            .order_by('-cuestionario__fecha_inicio', '-cuestionario__creado_en')
            .values_list('cuestionario_id', flat=True)
            .first()
        )
        if ultimo_id:
            cuestionarios = Cuestionario.objects.filter(
                id=ultimo_id
            ).select_related('periodo')
        else:
            cuestionarios = Cuestionario.objects.none()

    serializer = CuestionarioListSerializer(cuestionarios, many=True)

    return Response({
        'cuestionarios': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def detalle_cuestionario_tutor_view(request, cuestionario_id):
    """
    Detalle de un cuestionario específico
    GET /api/academic/cuestionarios/{id}/
    """
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )
    
    tiene_acceso = Grupo.objects.filter(
        tutor=request.docente,
        periodo=cuestionario.periodo,
    ).exists()
    
    if not tiene_acceso:
        return Response({
            'error': 'No tienes acceso a este cuestionario'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = CuestionarioDetailSerializer(cuestionario)
    
    return Response({
        'cuestionario': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def progreso_cuestionario_view(request, cuestionario_id):
    """
    Ver progreso de todos los grupos del tutor en un cuestionario.
    Si se especifica ?grupo_id=X, incluye lista de alumnos con fechas.

    GET /api/academic/cuestionarios/{id}/progreso/
    GET /api/academic/cuestionarios/{id}/progreso/?grupo_id={id}
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)

    grupos_tutor = Grupo.objects.filter(
        tutor=request.docente,
        periodo=cuestionario.periodo,
    ).select_related('periodo')

    if not grupos_tutor.exists():
        return Response({
            'error': 'No tienes grupos en este periodo'
        }, status=status.HTTP_403_FORBIDDEN)

    grupo_id = request.query_params.get('grupo_id')

    if grupo_id:
        grupos_tutor = grupos_tutor.filter(id=grupo_id)
        if not grupos_tutor.exists():
            return Response({
                'error': 'No tienes acceso a este grupo'
            }, status=status.HTTP_403_FORBIDDEN)

    grupos_ids = list(grupos_tutor.values_list('id', flat=True))

    # Una sola query para todos los conteos de estados
    estados_agg = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        grupo_id__in=grupos_ids
    ).values('grupo_id').annotate(
        total=Count('id'),
        completados=Count(Case(When(estado='COMPLETADO', then=1), output_field=IntegerField())),
        en_progreso=Count(Case(When(estado='EN_PROGRESO', then=1), output_field=IntegerField())),
        pendientes=Count(Case(When(estado='PENDIENTE', then=1), output_field=IntegerField())),
    )

    estados_por_grupo = {e['grupo_id']: e for e in estados_agg}

    # Si viene grupo_id, cargar detalle de alumnos con fechas — una sola query
    alumnos_por_grupo = {}
    if grupo_id:
        estados_detalle = CuestionarioEstado.objects.filter(
            cuestionario=cuestionario,
            grupo_id__in=grupos_ids
        ).select_related(
            'alumno', 'alumno__user'
        ).order_by('alumno__user__last_name', 'alumno__user__first_name')

        for estado in estados_detalle:
            gid = estado.grupo_id
            if gid not in alumnos_por_grupo:
                alumnos_por_grupo[gid] = []

            tiempo_transcurrido = None
            if estado.fecha_inicio and estado.fecha_fin:
                delta = estado.fecha_fin - estado.fecha_inicio
                minutos = int(delta.total_seconds() // 60)
                segundos = int(delta.total_seconds() % 60)
                tiempo_transcurrido = f"{minutos}m {segundos}s"

            numero_lista = len(alumnos_por_grupo[gid]) + 1
            alumnos_por_grupo[gid].append({
                'numero_lista': numero_lista,
                'alumno_id': estado.alumno.id,
                'matricula': estado.alumno.matricula,
                'nombre': f"{estado.alumno.user.last_name} {estado.alumno.user.first_name}".strip(),
                'estado': estado.estado,
                'fecha_inicio': estado.fecha_inicio,
                'fecha_fin': estado.fecha_fin,
                'tiempo_transcurrido': tiempo_transcurrido,
            })

    grupos_data = []
    for grupo in grupos_tutor:
        e = estados_por_grupo.get(grupo.id, {
            'total': 0, 'completados': 0, 'en_progreso': 0, 'pendientes': 0
        })
        total = e['total']
        completados = e['completados']
        porcentaje = round(completados / total * 100, 2) if total > 0 else 0

        grupo_data = {
            'grupo_id': grupo.id,
            'grupo_clave': grupo.clave,
            'total_alumnos': total,
            'completados': completados,
            'en_progreso': e['en_progreso'],
            'pendientes': e['pendientes'],
            'porcentaje_completado': porcentaje
        }

        # Solo incluir detalle de alumnos si se pidió grupo específico
        if grupo_id:
            grupo_data['alumnos'] = alumnos_por_grupo.get(grupo.id, [])

        grupos_data.append(grupo_data)

    return Response({
        'cuestionario_id': cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'total_grupos': len(grupos_data),
        'grupos': grupos_data
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def estadisticas_cuestionario_view(request, cuestionario_id):
    """
    Estadísticas sociométricas por grupo (DATA PARA SOCIOGRAMA)
    GET /api/academic/cuestionarios/{id}/estadisticas/
    Query params:
    - grupo_id: ID del grupo específico (opcional)
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    grupo_id = request.query_params.get('grupo_id')
    
    grupos_query = Grupo.objects.filter(
        tutor=request.docente,
        periodo=cuestionario.periodo,
    )
    
    if grupo_id:
        grupos_query = grupos_query.filter(id=grupo_id)
    
    grupos = grupos_query.select_related('periodo')
    
    if not grupos.exists():
        return Response({
            'error': 'No tienes grupos en este cuestionario'
        }, status=status.HTTP_403_FORBIDDEN)
    
    grupos_data = []
    
    for grupo in grupos:
        nodos_data = _calcular_nodos_sociograma(cuestionario, grupo)
        conexiones_data = _calcular_conexiones_sociograma(cuestionario, grupo)
        
        grupos_data.append({
            'grupo_id': grupo.id,
            'grupo_clave': grupo.clave,
            'total_alumnos': nodos_data['total_alumnos'],
            'respuestas_completas': nodos_data['respuestas_completas'],
            'nodos': nodos_data['nodos'],
            'conexiones': conexiones_data
        })
    
    return Response({
        'cuestionario_id': cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'total_grupos': len(grupos_data),
        'grupos': grupos_data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def registro_cuestionario_view(request, cuestionario_id):
    """
    Registro detallado de actividad por alumno en un grupo específico.
    grupo_id es requerido.

    GET /api/academic/cuestionarios/{id}/registro/?grupo_id={id}

    Response:
    {
        "cuestionario_id": 1,
        "cuestionario_titulo": "...",
        "grupo_id": 1,
        "grupo_clave": "IDGS-5-A",
        "resumen": {
            "total": 25,
            "completados": 18,
            "en_progreso": 4,
            "pendientes": 3,
            "porcentaje_completado": 72.0
        },
        "alumnos": [
            {
                "alumno_id": 1,
                "matricula": "UP210001",
                "nombre": "Juan Pérez López",
                "estado": "COMPLETADO",
                "fecha_inicio": "2026-02-10T09:15:00Z",
                "fecha_fin": "2026-02-10T09:45:00Z",
                "tiempo_transcurrido": "30m 0s"
            }
        ]
    }
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)

    grupo_id = request.query_params.get('grupo_id')

    if not grupo_id:
        return Response({
            'error': 'El parámetro grupo_id es requerido'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verificar que el grupo pertenece al tutor
    grupo = Grupo.objects.filter(
        id=grupo_id,
        tutor=request.docente,
        periodo=cuestionario.periodo,
    ).first()

    if not grupo:
        return Response({
            'error': 'No tienes acceso a este grupo'
        }, status=status.HTTP_403_FORBIDDEN)

    # Obtener todos los estados del grupo — una sola query
    estados = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        grupo=grupo
    ).select_related(
        'alumno', 'alumno__user'
    ).order_by('alumno__user__last_name', 'alumno__user__first_name')

    # Construir lista de alumnos y resumen en una sola pasada
    alumnos_data = []
    total = 0
    completados = 0
    en_progreso = 0
    pendientes = 0

    for estado in estados:
        total += 1

        if estado.estado == 'COMPLETADO':
            completados += 1
        elif estado.estado == 'EN_PROGRESO':
            en_progreso += 1
        else:
            pendientes += 1

        tiempo_transcurrido = None
        if estado.fecha_inicio and estado.fecha_fin:
            delta = estado.fecha_fin - estado.fecha_inicio
            minutos = int(delta.total_seconds() // 60)
            segundos = int(delta.total_seconds() % 60)
            tiempo_transcurrido = f"{minutos}m {segundos}s"

        alumnos_data.append({
            'numero_lista': total,
            'alumno_id': estado.alumno.id,
            'matricula': estado.alumno.matricula,
            'nombre': f"{estado.alumno.user.last_name} {estado.alumno.user.first_name}".strip(),
            'estado': estado.estado,
            'fecha_inicio': estado.fecha_inicio,
            'fecha_fin': estado.fecha_fin,
            'tiempo_transcurrido': tiempo_transcurrido,
        })

    porcentaje = round(completados / total * 100, 2) if total > 0 else 0

    return Response({
        'cuestionario_id': cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'grupo_id': grupo.id,
        'grupo_clave': grupo.clave,
        'resumen': {
            'total': total,
            'completados': completados,
            'en_progreso': en_progreso,
            'pendientes': pendientes,
            'porcentaje_completado': porcentaje,
        },
        'alumnos': alumnos_data,
    }, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def clasificacion_por_pregunta_view(request, cuestionario_id):
    """
    Ranking de alumnos por puntos recibidos en una pregunta específica.
    Solo aplica a preguntas de tipo SELECCION_ALUMNO.

    GET /api/academic/cuestionarios/{id}/clasificacion-pregunta/
    Query params:
    - grupo_id: requerido
    - pregunta_id: requerido (debe pertenecer al cuestionario)

    Response:
    {
        "cuestionario_id": 1,
        "cuestionario_titulo": "...",
        "grupo_id": 1,
        "grupo_clave": "IDGS-5-A",
        "pregunta_id": 3,
        "pregunta_texto": "¿Con quién harías equipo?",
        "pregunta_polaridad": "POSITIVA",
        "ranking": [
            {
                "rank": 1,
                "numero_lista": 4,
                "alumno_id": 12,
                "matricula": "UP210042",
                "nombre": "García López Juan Carlos",
                "puntaje_recibido": 9
            }
        ]
    }
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)

    grupo_id   = request.query_params.get('grupo_id')
    pregunta_id = request.query_params.get('pregunta_id')

    if not grupo_id:
        return Response(
            {'error': 'El parámetro grupo_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    if not pregunta_id:
        return Response(
            {'error': 'El parámetro pregunta_id es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verificar acceso del tutor al grupo
    grupo = Grupo.objects.filter(
        id=grupo_id,
        tutor=request.docente,
        periodo=cuestionario.periodo,
    ).first()

    if not grupo:
        return Response(
            {'error': 'No tienes acceso a este grupo'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Verificar que la pregunta pertenece al cuestionario y es de selección
    cp = cuestionario.preguntas.select_related('pregunta').filter(
        pregunta_id=pregunta_id
    ).first()

    if not cp:
        return Response(
            {'error': 'La pregunta no pertenece a este cuestionario'},
            status=status.HTTP_400_BAD_REQUEST
        )

    pregunta = cp.pregunta

    if pregunta.tipo != 'SELECCION_ALUMNO':
        return Response(
            {'error': 'Solo se puede clasificar por preguntas de tipo SELECCION_ALUMNO'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Alumnos del grupo ordenados alfabéticamente (para numero_lista consistente)
    alumnos_grupo = AlumnoGrupo.objects.filter(
        grupo=grupo,
        activo=True
    ).select_related('alumno', 'alumno__user').order_by(
        'alumno__user__last_name', 'alumno__user__first_name'
    )

    alumnos_ids = [ag.alumno_id for ag in alumnos_grupo]

    # Puntos recibidos por alumno en esta pregunta — una sola query
    puntajes_qs = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta=pregunta,
        seleccionado_alumno_id__in=alumnos_ids
    ).values('seleccionado_alumno_id').annotate(
        puntaje_total=Sum('puntaje')
    )

    puntajes_map = {r['seleccionado_alumno_id']: r['puntaje_total'] or 0 for r in puntajes_qs}

    # Asignar numero_lista y puntaje a cada alumno
    alumnos_con_puntaje = []
    for numero_lista, ag in enumerate(alumnos_grupo, start=1):
        alumnos_con_puntaje.append({
            'numero_lista': numero_lista,
            'alumno_id': ag.alumno.id,
            'matricula': ag.alumno.matricula,
            'nombre': f"{ag.alumno.user.last_name} {ag.alumno.user.first_name}".strip(),
            'puntaje_recibido': puntajes_map.get(ag.alumno_id, 0),
        })

    # Ordenar por puntaje descendente y asignar rank
    alumnos_con_puntaje.sort(key=lambda x: x['puntaje_recibido'], reverse=True)

    ranking = []
    for rank, alumno in enumerate(alumnos_con_puntaje, start=1):
        ranking.append({
            'rank': rank,
            'numero_lista': alumno['numero_lista'],
            'alumno_id': alumno['alumno_id'],
            'matricula': alumno['matricula'],
            'nombre': alumno['nombre'],
            'puntaje_recibido': alumno['puntaje_recibido'],
        })

    return Response({
        'cuestionario_id': cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'grupo_id': grupo.id,
        'grupo_clave': grupo.clave,
        'pregunta_id': pregunta.id,
        'pregunta_texto': pregunta.texto,
        'pregunta_polaridad': pregunta.polaridad,
        'ranking': ranking,
    }, status=status.HTTP_200_OK)


# ============================================
# FUNCIONES HELPER
# ============================================

def _calcular_nodos_sociograma(cuestionario, grupo):
    """
    Calcula nodos con clasificación sociométrica.
    Queries totales: 5 (independiente del número de alumnos)
      1. AlumnoGrupo del grupo
      2. IDs preguntas positivas
      3. IDs preguntas negativas
      4. Puntos recibidos por alumno (annotate en batch)
      5. Estados por alumno
    """
    # 1. Alumnos del grupo
    alumnos_grupo = AlumnoGrupo.objects.filter(
        grupo=grupo,
        activo=True
    ).select_related('alumno', 'alumno__user').order_by(
        'alumno__user__last_name', 'alumno__user__first_name'
    )
    
    total_alumnos = alumnos_grupo.count()
    alumnos_ids = list(alumnos_grupo.values_list('alumno_id', flat=True))

    # 2 y 3. IDs de preguntas por polaridad
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

    # 4. Puntos y conteos por alumno — una sola query con annotate
    puntos_por_alumno = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id__in=todas_preguntas_ids,
        seleccionado_alumno_id__in=alumnos_ids
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

    # Elecciones realizadas por alumno — una query
    elecciones_realizadas_qs = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id__in=todas_preguntas_ids,
        alumno_id__in=alumnos_ids,
        seleccionado_alumno__isnull=False
    ).values('alumno_id').annotate(total=Count('id'))

    # Estados por alumno — una query
    estados_qs = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        alumno_id__in=alumnos_ids,
        grupo=grupo
    ).values('alumno_id', 'estado')

    # Indexar resultados para lookup O(1)
    puntos_map = {r['seleccionado_alumno_id']: r for r in puntos_por_alumno}
    realizadas_map = {r['alumno_id']: r['total'] for r in elecciones_realizadas_qs}
    estados_map = {r['alumno_id']: r['estado'] for r in estados_qs}

    # Calcular max_impacto en memoria (sin queries adicionales)
    max_impacto = 0
    for alumno_id in alumnos_ids:
        p = puntos_map.get(alumno_id, {})
        pos = p.get('puntos_positivos') or 0
        neg = p.get('puntos_negativos') or 0
        impacto = pos + neg
        if impacto > max_impacto:
            max_impacto = impacto

    # Construir nodos
    nodos = []
    respuestas_completas = 0

    for numero_lista, ag in enumerate(alumnos_grupo, start=1):
        alumno = ag.alumno
        p = puntos_map.get(alumno.id, {})

        puntos_positivos = p.get('puntos_positivos') or 0
        puntos_negativos = p.get('puntos_negativos') or 0
        impacto_total = puntos_positivos + puntos_negativos
        elecciones_recibidas = p.get('elecciones_recibidas') or 0
        elecciones_realizadas = realizadas_map.get(alumno.id, 0)
        estado = estados_map.get(alumno.id, 'PENDIENTE')

        if estado == 'COMPLETADO':
            respuestas_completas += 1

        tipo = _clasificar_alumno(
            puntos_positivos,
            puntos_negativos,
            impacto_total,
            max_impacto
        )

        nodos.append({
            'numero_lista': numero_lista,
            'alumno_id': alumno.id,
            'matricula': alumno.matricula,
            'nombre': f"{alumno.user.last_name} {alumno.user.first_name}".strip(),
            'tipo': tipo,
            'puntos_positivos': puntos_positivos,
            'puntos_negativos': puntos_negativos,
            'impacto_total': impacto_total,
            'tamano': impacto_total,
            'elecciones_recibidas': elecciones_recibidas,
            'elecciones_realizadas': elecciones_realizadas,
            'completo': estado == 'COMPLETADO'
        })

    return {
        'total_alumnos': total_alumnos,
        'respuestas_completas': respuestas_completas,
        'nodos': nodos
    }


def _calcular_conexiones_sociograma(cuestionario, grupo):
    """
    Calcula conexiones con pesos.
    Queries totales: 3 (independiente del número de alumnos)
      1. IDs alumnos del grupo
      2. IDs preguntas sociométricas + max_elecciones
      3. Todas las respuestas del grupo en una query
    """
    alumnos_ids = list(
        AlumnoGrupo.objects.filter(grupo=grupo, activo=True)
        .values_list('alumno_id', flat=True)
    )

    # Preguntas sociométricas con sus datos — evita Pregunta.objects.get() en loop
    preguntas_socio = list(
        cuestionario.preguntas.filter(
            pregunta__tipo='SELECCION_ALUMNO'
        ).select_related('pregunta').values(
            'pregunta_id',
            'pregunta__max_elecciones',
            'pregunta__polaridad'
        )
    )
    preguntas_ids = [p['pregunta_id'] for p in preguntas_socio]

    # Calcular total de puntos posibles en memoria
    total_puntos_posibles = sum(
        len(alumnos_ids) * p['pregunta__max_elecciones'] * p['pregunta__max_elecciones']
        for p in preguntas_socio
    )

    # Todas las respuestas del grupo en una sola query
    respuestas = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id__in=preguntas_ids,
        alumno_id__in=alumnos_ids,
        seleccionado_alumno_id__in=alumnos_ids
    ).select_related(
        'alumno__user',
        'seleccionado_alumno__user',
        'pregunta'
    )

    # Agrupar en memoria
    conexiones_dict = {}

    for resp in respuestas:
        key = (resp.alumno.id, resp.seleccionado_alumno.id)

        if key not in conexiones_dict:
            conexiones_dict[key] = {
                'origen_id': resp.alumno.id,
                'origen_nombre': f"{resp.alumno.user.last_name} {resp.alumno.user.first_name}".strip(),
                'destino_id': resp.seleccionado_alumno.id,
                'destino_nombre': f"{resp.seleccionado_alumno.user.last_name} {resp.seleccionado_alumno.user.first_name}".strip(),
                'peso_total': 0,
                'polaridad': resp.pregunta.polaridad
            }

        conexiones_dict[key]['peso_total'] += resp.puntaje or 1

    # Calcular tipo de conexión en memoria
    conexiones = []

    for key, data in conexiones_dict.items():
        origen_id, destino_id = key
        key_inversa = (destino_id, origen_id)

        if key_inversa in conexiones_dict:
            puntos_mutuos = data['peso_total'] + conexiones_dict[key_inversa]['peso_total']
        else:
            puntos_mutuos = data['peso_total']

        porcentaje_mutuo = (
            round(puntos_mutuos / total_puntos_posibles * 100, 2)
            if total_puntos_posibles > 0 else 0
        )

        tipo_conexion = 'fuerte' if porcentaje_mutuo >= 33 else 'debil'

        conexiones.append({
            'origen_id': data['origen_id'],
            'origen_nombre': data['origen_nombre'],
            'destino_id': data['destino_id'],
            'destino_nombre': data['destino_nombre'],
            'peso': data['peso_total'],
            'tipo_conexion': tipo_conexion,
            'porcentaje_mutuo': porcentaje_mutuo,
            'es_mutua': key_inversa in conexiones_dict,
            'polaridad': data['polaridad']
        })

    return conexiones


def _clasificar_alumno(puntos_positivos, puntos_negativos, impacto_total, max_impacto):
    """
    Clasifica al alumno según su impacto sociométrico.
    INVISIBLE: impacto <= 5% del máximo
    ACEPTADO: positivos > negativos (o empate)
    RECHAZADO: negativos > positivos
    """
    umbral_invisible = max_impacto * 0.05

    if impacto_total <= umbral_invisible:
        return 'INVISIBLE'

    if puntos_positivos >= puntos_negativos:
        return 'ACEPTADO'

    return 'RECHAZADO'