# core/views/admin/cuestionarios.py
"""
Endpoints para gestión de cuestionarios (Admin)
REFACTORIZADO: Cuestionarios por PERIODO
ACTUALIZADO Fase 3: asociar_pregunta_view — asociar pregunta existente del banco
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.shortcuts import get_object_or_404

from core.models import (
    Cuestionario, CuestionarioPregunta, CuestionarioEstado, 
    Pregunta, Periodo, Grupo, AlumnoGrupo
)
from core.serializers import (
    CuestionarioListSerializer,
    CuestionarioDetailSerializer,
    CuestionarioCreateSerializer,
    CuestionarioUpdateSerializer,
    AgregarPreguntaSerializer,
    CuestionarioPreguntaSerializer,
)
from core.utils.decorators import require_admin


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def crear_cuestionario_view(request):
    """
    Crea un nuevo cuestionario para un periodo

    POST /api/admin/cuestionarios/crear/

    Body:
    {
        "titulo": "Cuestionario Sociométrico Febrero 2026",
        "descripcion": "Cuestionario para análisis de relaciones",
        "periodo": 1,
        "fecha_inicio": "2026-02-15T08:00:00Z",
        "fecha_fin": "2026-02-20T23:59:59Z",
        "activo": false,
        "preguntas_ids": [1, 2, 3],
        "preguntas": [...]
    }
    """
    serializer = CuestionarioCreateSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    cuestionario = serializer.save()
    detail_serializer = CuestionarioDetailSerializer(cuestionario)
    
    return Response({
        'success': True,
        'cuestionario': detail_serializer.data,
        'message': 'Cuestionario creado. Actívalo para que los grupos puedan responderlo.'
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_admin
def listar_cuestionarios_view(request):
    """
    Lista todos los cuestionarios

    GET /api/admin/cuestionarios/

    Query params:
    - periodo: ID del periodo (opcional)
    - activo: true/false (opcional)
    """
    cuestionarios = Cuestionario.objects.select_related('periodo').all()
    
    periodo_id = request.query_params.get('periodo')
    activo = request.query_params.get('activo')
    
    if periodo_id:
        cuestionarios = cuestionarios.filter(periodo_id=periodo_id)
    
    if activo is not None:
        activo_bool = activo.lower() == 'true'
        cuestionarios = cuestionarios.filter(activo=activo_bool)
    
    cuestionarios = cuestionarios.order_by('-creado_en')
    serializer = CuestionarioListSerializer(cuestionarios, many=True)
    
    return Response({
        'cuestionarios': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_admin
def detalle_cuestionario_view(request, cuestionario_id):
    """
    Detalle completo de un cuestionario

    GET /api/admin/cuestionarios/{id}/
    """
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )
    
    serializer = CuestionarioDetailSerializer(cuestionario)
    
    return Response({
        'cuestionario': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@require_admin
def actualizar_cuestionario_view(request, cuestionario_id):
    """
    Actualiza un cuestionario

    PUT /api/admin/cuestionarios/{id}/actualizar/
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    serializer = CuestionarioUpdateSerializer(cuestionario, data=request.data, partial=True)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    cuestionario = serializer.save()
    detail_serializer = CuestionarioDetailSerializer(cuestionario)
    
    return Response({
        'success': True,
        'cuestionario': detail_serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@require_admin
def eliminar_cuestionario_view(request, cuestionario_id):
    """
    Elimina un cuestionario

    DELETE /api/admin/cuestionarios/{id}/eliminar/
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    if cuestionario.total_respuestas > 0:
        return Response({
            'success': False,
            'error': 'No se puede eliminar un cuestionario que ya tiene respuestas',
            'respuestas_count': cuestionario.total_respuestas
        }, status=status.HTTP_400_BAD_REQUEST)
    
    titulo = cuestionario.titulo
    cuestionario.delete()
    
    return Response({
        'success': True,
        'message': f'Cuestionario "{titulo}" eliminado correctamente'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def activar_cuestionario_view(request, cuestionario_id):
    """
    Activa un cuestionario y crea estados para todos los alumnos del periodo.
    Desactiva automáticamente otros cuestionarios activos del mismo periodo.

    POST /api/admin/cuestionarios/{id}/activar/
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    if cuestionario.total_preguntas == 0:
        return Response({
            'success': False,
            'error': 'No se puede activar un cuestionario sin preguntas'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    with transaction.atomic():
        cuestionarios_desactivados = Cuestionario.objects.filter(
            periodo=cuestionario.periodo,
            activo=True
        ).exclude(id=cuestionario_id).update(activo=False)
        
        cuestionario.activo = True
        cuestionario.save()
        
        estados_creados = _crear_estados_para_periodo(cuestionario)
    
    serializer = CuestionarioDetailSerializer(cuestionario)
    
    return Response({
        'success': True,
        'cuestionario': serializer.data,
        'estados_creados': estados_creados['total'],
        'grupos_afectados': estados_creados['grupos_count'],
        'cuestionarios_desactivados': cuestionarios_desactivados
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def desactivar_cuestionario_view(request, cuestionario_id):
    """
    Desactiva un cuestionario

    POST /api/admin/cuestionarios/{id}/desactivar/
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    cuestionario.activo = False
    cuestionario.save()
    
    serializer = CuestionarioDetailSerializer(cuestionario)
    
    return Response({
        'success': True,
        'cuestionario': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def agregar_pregunta_view(request, cuestionario_id):
    """
    Agrega una pregunta NUEVA a un cuestionario existente.
    La pregunta se crea en el banco y se asocia al cuestionario.

    POST /api/admin/cuestionarios/{id}/agregar-pregunta/

    Body:
    {
        "texto": "¿Nueva pregunta?",
        "tipo": "SELECCION_ALUMNO",
        "polaridad": "POSITIVA",
        "max_elecciones": 3,
        "descripcion": "Opcional"
    }
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    serializer = AgregarPreguntaSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    ultimo_orden = CuestionarioPregunta.objects.filter(
        cuestionario=cuestionario
    ).count()
    nuevo_orden = ultimo_orden + 1
    
    pregunta = Pregunta.objects.create(
        texto=serializer.validated_data['texto'],
        tipo=serializer.validated_data['tipo'],
        polaridad=serializer.validated_data.get('polaridad', 'POSITIVA'),
        max_elecciones=serializer.validated_data.get('max_elecciones', 3),
        descripcion=serializer.validated_data.get('descripcion', ''),
        orden=nuevo_orden,
        activa=True
    )
    
    cuestionario_pregunta = CuestionarioPregunta.objects.create(
        cuestionario=cuestionario,
        pregunta=pregunta,
        orden=nuevo_orden
    )
    
    response_serializer = CuestionarioPreguntaSerializer(cuestionario_pregunta)
    
    return Response({
        'success': True,
        'cuestionario_pregunta': response_serializer.data,
        'total_preguntas': cuestionario.total_preguntas
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def asociar_pregunta_view(request, cuestionario_id):
    """
    Asocia una pregunta EXISTENTE del banco a un cuestionario.
    Se crea una COPIA de la pregunta — el original del banco queda intacto
    y puede eliminarse o editarse sin afectar el cuestionario.

    POST /api/admin/cuestionarios/{id}/asociar-pregunta/

    Body:
    {
        "pregunta_id": 5
    }
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)

    pregunta_id = request.data.get('pregunta_id')

    if not pregunta_id:
        return Response({
            'success': False,
            'error': 'El campo pregunta_id es requerido.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verificar que la pregunta exista y esté activa
    pregunta_banco = get_object_or_404(Pregunta, id=pregunta_id, activa=True)

    # Determinar orden
    ultimo_orden = CuestionarioPregunta.objects.filter(
        cuestionario=cuestionario
    ).count()
    nuevo_orden = ultimo_orden + 1

    # Clonar la pregunta del banco
    from core.serializers.cuestionario import _clonar_pregunta
    copia = _clonar_pregunta(pregunta_banco, nuevo_orden)

    cuestionario_pregunta = CuestionarioPregunta.objects.create(
        cuestionario=cuestionario,
        pregunta=copia,
        orden=nuevo_orden
    )

    response_serializer = CuestionarioPreguntaSerializer(cuestionario_pregunta)

    return Response({
        'success': True,
        'cuestionario_pregunta': response_serializer.data,
        'total_preguntas': cuestionario.total_preguntas
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@require_admin
def remover_pregunta_view(request, cuestionario_id, pregunta_id):
    """
    Remueve una pregunta de un cuestionario

    DELETE /api/admin/cuestionarios/{id}/remover-pregunta/{pregunta_id}/
    """
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    cuestionario_pregunta = get_object_or_404(
        CuestionarioPregunta,
        cuestionario=cuestionario,
        pregunta_id=pregunta_id
    )
    
    from core.models import Respuesta
    respuestas_count = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id=pregunta_id
    ).count()
    
    if respuestas_count > 0:
        return Response({
            'success': False,
            'error': 'No se puede remover una pregunta que ya tiene respuestas',
            'respuestas_count': respuestas_count
        }, status=status.HTTP_400_BAD_REQUEST)
    
    cuestionario_pregunta.delete()
    
    # Reordenar
    preguntas_restantes = CuestionarioPregunta.objects.filter(
        cuestionario=cuestionario
    ).order_by('orden')
    
    for idx, cp in enumerate(preguntas_restantes, start=1):
        if cp.orden != idx:
            cp.orden = idx
            cp.save()
    
    return Response({
        'success': True,
        'message': 'Pregunta removida correctamente',
        'total_preguntas': cuestionario.total_preguntas
    }, status=status.HTTP_200_OK)


# ============================================
# FUNCIONES HELPER
# ============================================

def _crear_estados_para_periodo(cuestionario):
    """
    Crea estados para todos los alumnos activos de todos los grupos del periodo
    """
    grupos = Grupo.objects.filter(
        periodo=cuestionario.periodo,
        activo=True
    )
    
    estados_creados = []
    grupos_count = 0
    
    for grupo in grupos:
        alumnos_grupo = AlumnoGrupo.objects.filter(
            grupo=grupo,
            activo=True
        ).select_related('alumno')
        
        if alumnos_grupo.exists():
            grupos_count += 1
            
            for ag in alumnos_grupo:
                estado, created = CuestionarioEstado.objects.get_or_create(
                    cuestionario=cuestionario,
                    alumno=ag.alumno,
                    grupo=grupo,
                    defaults={
                        'estado': 'PENDIENTE',
                        'progreso': 0.00
                    }
                )
                
                if created:
                    estados_creados.append(estado)
    
    return {
        'total': len(estados_creados),
        'grupos_count': grupos_count
    }