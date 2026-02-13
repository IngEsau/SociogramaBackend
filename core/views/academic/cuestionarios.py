# core/views/academic/cuestionarios.py
"""
Endpoints para Tutores - Gestión de Cuestionarios
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Avg

from core.models import (
    Cuestionario, CuestionarioEstado, Grupo, Respuesta, Pregunta, Alumno
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
    
    Response:
    {
        "cuestionarios": [...]
    }
    """
    # Obtener grupos del tutor
    grupos_tutor = Grupo.objects.filter(
        tutor=request.docente,
        activo=True,
        periodo__activo=True
    ).values_list('periodo_id', flat=True).distinct()
    
    # Cuestionarios activos de esos periodos
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
    
    # Verificar que el tutor tenga acceso (sus grupos están en ese periodo)
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
    
    Response:
    {
        "cuestionario_id": 1,
        "cuestionario_titulo": "...",
        "grupos": [
            {
                "grupo_id": 1,
                "grupo_clave": "1A",
                "total_alumnos": 25,
                "completados": 20,
                "en_progreso": 3,
                "pendientes": 2,
                "porcentaje_completado": 80.0
            }
        ]
    }
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    # Obtener grupos del tutor en el periodo del cuestionario
    grupos_tutor = Grupo.objects.filter(
        tutor=request.docente,
        periodo=cuestionario.periodo,
        activo=True
    ).select_related('periodo')
    
    if not grupos_tutor.exists():
        return Response({
            'error': 'No tienes grupos en este periodo'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Calcular progreso por grupo
    grupos_data = []
    for grupo in grupos_tutor:
        estados = CuestionarioEstado.objects.filter(
            cuestionario=cuestionario,
            grupo=grupo
        )
        
        total_alumnos = estados.count()
        completados = estados.filter(estado='COMPLETADO').count()
        en_progreso = estados.filter(estado='EN_PROGRESO').count()
        pendientes = estados.filter(estado='PENDIENTE').count()
        
        porcentaje = (completados / total_alumnos * 100) if total_alumnos > 0 else 0
        
        grupos_data.append({
            'grupo_id': grupo.id,
            'grupo_clave': grupo.clave,
            'total_alumnos': total_alumnos,
            'completados': completados,
            'en_progreso': en_progreso,
            'pendientes': pendientes,
            'porcentaje_completado': round(porcentaje, 2)
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
    - grupo_id: ID del grupo específico (opcional, si no se proporciona muestra todos)
    
    Response:
    {
        "cuestionario_id": 1,
        "cuestionario_titulo": "...",
        "grupos": [
            {
                "grupo_id": 1,
                "grupo_clave": "1A",
                "total_alumnos": 25,
                "respuestas_completas": 20,
                "nodos": [
                    {
                        "alumno_id": 1,
                        "matricula": "UTP001",
                        "nombre": "Juan Pérez",
                        "tipo": "ACEPTADO",
                        "puntos_recibidos": 48,
                        "elecciones_recibidas": 12,
                        "elecciones_realizadas": 3
                    }
                ],
                "conexiones": [
                    {
                        "origen_id": 2,
                        "origen_nombre": "María García",
                        "destino_id": 1,
                        "destino_nombre": "Juan Pérez",
                        "peso": 3,
                        "tipo_conexion": "fuerte"
                    }
                ]
            }
        ]
    }
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    # Filtro opcional por grupo
    grupo_id = request.query_params.get('grupo_id')
    
    # Obtener grupos del tutor
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
    
    # Generar estadísticas por grupo
    grupos_data = []
    
    for grupo in grupos:
        # Calcular nodos y conexiones
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
# FUNCIONES HELPER
# ============================================

def _calcular_nodos_sociograma(cuestionario, grupo):
    """
    Calcula nodos (alumnos) con clasificación sociométrica
    """
    from core.models import AlumnoGrupo
    
    # Obtener alumnos del grupo
    alumnos_grupo = AlumnoGrupo.objects.filter(
        grupo=grupo,
        activo=True
    ).select_related('alumno', 'alumno__user')
    
    total_alumnos = alumnos_grupo.count()
    
    # Obtener preguntas sociométricas del cuestionario
    preguntas_socio = cuestionario.preguntas.filter(
        pregunta__tipo='SELECCION_ALUMNO'
    ).values_list('pregunta_id', flat=True)
    
    nodos = []
    respuestas_completas = 0
    
    for ag in alumnos_grupo:
        alumno = ag.alumno
        
        # Contar elecciones RECIBIDAS (cuántos lo eligieron)
        elecciones_recibidas = Respuesta.objects.filter(
            cuestionario=cuestionario,
            pregunta_id__in=preguntas_socio,
            seleccionado_alumno=alumno
        ).count()
        
        # Sumar puntos recibidos
        puntos_recibidos = Respuesta.objects.filter(
            cuestionario=cuestionario,
            pregunta_id__in=preguntas_socio,
            seleccionado_alumno=alumno
        ).aggregate(
            total=Count('puntaje')
        )['total'] or 0
        
        # Contar elecciones REALIZADAS (cuántos eligió)
        elecciones_realizadas = Respuesta.objects.filter(
            cuestionario=cuestionario,
            pregunta_id__in=preguntas_socio,
            alumno=alumno,
            seleccionado_alumno__isnull=False
        ).count()
        
        # Verificar si completó el cuestionario
        estado = CuestionarioEstado.objects.filter(
            cuestionario=cuestionario,
            alumno=alumno,
            grupo=grupo
        ).first()
        
        if estado and estado.estado == 'COMPLETADO':
            respuestas_completas += 1
        
        # Clasificar alumno (ACEPTADO/RECHAZADO/INVISIBLE)
        tipo = _clasificar_alumno(elecciones_recibidas, puntos_recibidos, total_alumnos)
        
        nodos.append({
            'alumno_id': alumno.id,
            'matricula': alumno.matricula,
            'nombre': alumno.user.nombre_completo,
            'tipo': tipo,
            'puntos_recibidos': puntos_recibidos,
            'elecciones_recibidas': elecciones_recibidas,
            'elecciones_realizadas': elecciones_realizadas,
            'completo': estado.estado == 'COMPLETADO' if estado else False
        })
    
    return {
        'total_alumnos': total_alumnos,
        'respuestas_completas': respuestas_completas,
        'nodos': nodos
    }


def _calcular_conexiones_sociograma(cuestionario, grupo):
    """
    Calcula conexiones (quién eligió a quién) con pesos
    """
    from core.models import AlumnoGrupo
    
    # IDs de alumnos del grupo
    alumnos_ids = AlumnoGrupo.objects.filter(
        grupo=grupo,
        activo=True
    ).values_list('alumno_id', flat=True)
    
    # Preguntas sociométricas
    preguntas_socio = cuestionario.preguntas.filter(
        pregunta__tipo='SELECCION_ALUMNO'
    ).values_list('pregunta_id', flat=True)
    
    # Obtener todas las respuestas de selección entre alumnos del grupo
    respuestas = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id__in=preguntas_socio,
        alumno_id__in=alumnos_ids,
        seleccionado_alumno_id__in=alumnos_ids
    ).select_related(
        'alumno', 'alumno__user',
        'seleccionado_alumno', 'seleccionado_alumno__user'
    )
    
    conexiones = []
    
    for resp in respuestas:
        # Clasificar tipo de conexión según puntaje
        if resp.puntaje >= 3:
            tipo_conexion = 'fuerte'
        elif resp.puntaje == 2:
            tipo_conexion = 'media'
        else:
            tipo_conexion = 'debil'
        
        conexiones.append({
            'origen_id': resp.alumno.id,
            'origen_nombre': resp.alumno.user.nombre_completo,
            'destino_id': resp.seleccionado_alumno.id,
            'destino_nombre': resp.seleccionado_alumno.user.nombre_completo,
            'peso': resp.puntaje or 1,
            'tipo_conexion': tipo_conexion,
            'orden_eleccion': resp.orden_eleccion
        })
    
    return conexiones


def _clasificar_alumno(elecciones_recibidas, puntos_recibidos, total_alumnos):
    """
    Clasifica al alumno según su popularidad sociométrica
    
    ACEPTADO: Más del 30% del grupo lo eligió
    RECHAZADO: Menos del 10% lo eligió PERO tiene elecciones
    INVISIBLE: 0 elecciones recibidas
    """
    if elecciones_recibidas == 0:
        return 'INVISIBLE'
    
    porcentaje = (elecciones_recibidas / total_alumnos) * 100
    
    if porcentaje >= 30:
        return 'ACEPTADO'
    elif porcentaje < 10:
        return 'RECHAZADO'
    else:
        return 'ACEPTADO'  # Neutral/Aceptado