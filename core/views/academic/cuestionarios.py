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
    Lista cuestionarios activos del periodo actual
    GET /api/academic/cuestionarios/
    """
    grupos_tutor = Grupo.objects.filter(
        tutor=request.docente,
        activo=True,
        periodo__activo=True
    ).values_list('periodo_id', flat=True).distinct()
    
    cuestionarios = Cuestionario.objects.filter(
        periodo_id__in=grupos_tutor,
        activo=True
    ).select_related('periodo').order_by('-creado_en')
    
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
        activo=True
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
    Ver progreso de todos los grupos del tutor en un cuestionario
    GET /api/academic/cuestionarios/{id}/progreso/
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    grupos_tutor = Grupo.objects.filter(
        tutor=request.docente,
        periodo=cuestionario.periodo,
        activo=True
    ).select_related('periodo')
    
    if not grupos_tutor.exists():
        return Response({
            'error': 'No tienes grupos en este periodo'
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
    
    # Indexar por grupo_id para lookup O(1)
    estados_por_grupo = {e['grupo_id']: e for e in estados_agg}
    
    grupos_data = []
    for grupo in grupos_tutor:
        e = estados_por_grupo.get(grupo.id, {
            'total': 0, 'completados': 0, 'en_progreso': 0, 'pendientes': 0
        })
        total = e['total']
        completados = e['completados']
        porcentaje = round(completados / total * 100, 2) if total > 0 else 0
        
        grupos_data.append({
            'grupo_id': grupo.id,
            'grupo_clave': grupo.clave,
            'total_alumnos': total,
            'completados': completados,
            'en_progreso': e['en_progreso'],
            'pendientes': e['pendientes'],
            'porcentaje_completado': porcentaje
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
        activo=True
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


# ============================================
# FUNCIONES HELPER — SIN N+1
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
    ).select_related('alumno', 'alumno__user')
    
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

    for ag in alumnos_grupo:
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
            'alumno_id': alumno.id,
            'matricula': alumno.matricula,
            'nombre': alumno.user.nombre_completo,
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
                'origen_nombre': resp.alumno.user.nombre_completo,
                'destino_id': resp.seleccionado_alumno.id,
                'destino_nombre': resp.seleccionado_alumno.user.nombre_completo,
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