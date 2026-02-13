# core/views/student/cuestionarios.py
"""
Endpoints para Estudiantes - Cuestionarios Sociométricos
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction

from core.models import (
    Cuestionario, CuestionarioEstado, Pregunta, Respuesta,
    AlumnoGrupo, Alumno
)
from core.serializers import (
    CuestionarioListSerializer,
    CuestionarioDetailSerializer,
    RespuestaCreateSerializer,
    ProgresoAlumnoSerializer,
)
from core.utils.decorators import require_alumno


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_alumno
def cuestionarios_disponibles_view(request):
    """
    Lista cuestionarios disponibles para el alumno
    
    GET /api/student/cuestionarios/disponibles/
    
    Response:
    {
        "cuestionarios": [...]
    }
    """
    alumno = request.alumno
    
    # Obtener grupo activo del alumno en periodo activo
    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=alumno,
        activo=True,
        grupo__activo=True,
        grupo__periodo__activo=True
    ).select_related('grupo', 'grupo__periodo').first()
    
    if not alumno_grupo:
        return Response({
            'cuestionarios': [],
            'message': 'No estás inscrito en ningún grupo activo'
        }, status=status.HTTP_200_OK)
    
    # Cuestionarios activos del periodo
    cuestionarios = Cuestionario.objects.filter(
        periodo=alumno_grupo.grupo.periodo,
        activo=True
    ).select_related('periodo').order_by('-creado_en')
    
    # Filtrar solo los que están en el rango de fechas
    cuestionarios_disponibles = [c for c in cuestionarios if c.esta_activo]
    
    serializer = CuestionarioListSerializer(cuestionarios_disponibles, many=True)
    
    return Response({
        'cuestionarios': serializer.data,
        'grupo_actual': {
            'id': alumno_grupo.grupo.id,
            'clave': alumno_grupo.grupo.clave
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_alumno
def detalle_cuestionario_alumno_view(request, cuestionario_id):
    """
    Detalle de un cuestionario específico
    
    GET /api/student/cuestionarios/{id}/
    """
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )
    
    # Verificar acceso
    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=request.alumno,
        grupo__periodo=cuestionario.periodo,
        activo=True
    ).first()
    
    if not alumno_grupo:
        return Response({
            'error': 'No tienes acceso a este cuestionario'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if not cuestionario.esta_activo:
        return Response({
            'error': 'Este cuestionario no está disponible en este momento'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = CuestionarioDetailSerializer(cuestionario)
    
    return Response({
        'cuestionario': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_alumno
def preguntas_cuestionario_view(request, cuestionario_id):
    """
    Obtiene preguntas del cuestionario con compañeros para seleccionar
    
    GET /api/student/cuestionarios/{id}/preguntas/
    
    Response:
    {
        "cuestionario_id": 1,
        "cuestionario_titulo": "...",
        "preguntas": [...],
        "companeros": [...]  // Para preguntas tipo SELECCION_ALUMNO
    }
    """
    alumno = request.alumno
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    # Verificar acceso
    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=alumno,
        grupo__periodo=cuestionario.periodo,
        activo=True
    ).select_related('grupo').first()
    
    if not alumno_grupo:
        return Response({
            'error': 'No tienes acceso a este cuestionario'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if not cuestionario.esta_activo:
        return Response({
            'error': 'Este cuestionario no está disponible'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Obtener preguntas ordenadas
    preguntas_cuestionario = cuestionario.preguntas.select_related('pregunta').order_by('orden')
    
    preguntas_data = []
    for cp in preguntas_cuestionario:
        pregunta = cp.pregunta
        
        # Verificar si ya respondió esta pregunta
        ya_respondio = Respuesta.objects.filter(
            alumno=alumno,
            cuestionario=cuestionario,
            pregunta=pregunta
        ).exists()
        
        preguntas_data.append({
            'id': pregunta.id,
            'texto': pregunta.texto,
            'tipo': pregunta.tipo,
            'max_elecciones': pregunta.max_elecciones,
            'descripcion': pregunta.descripcion,
            'orden': cp.orden,
            'ya_respondida': ya_respondio
        })
    
    # Obtener compañeros del grupo (excluyendo al alumno actual)
    companeros = AlumnoGrupo.objects.filter(
        grupo=alumno_grupo.grupo,
        activo=True
    ).exclude(
        alumno=alumno
    ).select_related('alumno', 'alumno__user').order_by('alumno__user__nombre_completo')
    
    companeros_data = [
        {
            'id': ag.alumno.id,
            'matricula': ag.alumno.matricula,
            'nombre': ag.alumno.user.nombre_completo
        }
        for ag in companeros
    ]
    
    return Response({
        'cuestionario_id': cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'grupo_id': alumno_grupo.grupo.id,
        'grupo_clave': alumno_grupo.grupo.clave,
        'preguntas': preguntas_data,
        'companeros': companeros_data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_alumno
def responder_cuestionario_view(request, cuestionario_id):
    """
    Guarda respuestas del cuestionario
    
    POST /api/student/cuestionarios/{id}/responder/
    
    Body:
    {
        "respuestas": [
            {
                "pregunta_id": 1,
                "seleccionados": [
                    {"alumno_id": 5, "orden": 1},
                    {"alumno_id": 8, "orden": 2},
                    {"alumno_id": 12, "orden": 3}
                ]
            },
            {
                "pregunta_id": 2,
                "seleccionados": [
                    {"alumno_id": 5, "orden": 1}
                ]
            }
        ]
    }
    """
    alumno = request.alumno
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    # Verificar acceso y grupo
    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=alumno,
        grupo__periodo=cuestionario.periodo,
        activo=True
    ).select_related('grupo').first()
    
    if not alumno_grupo:
        return Response({
            'error': 'No tienes acceso a este cuestionario'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if not cuestionario.esta_activo:
        return Response({
            'error': 'Este cuestionario no está disponible'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Verificar si ya completó el cuestionario
    estado = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        alumno=alumno,
        grupo=alumno_grupo.grupo
    ).first()
    
    if estado and estado.estado == 'COMPLETADO':
        return Response({
            'error': 'Ya completaste este cuestionario',
            'message': 'No puedes volver a responder un cuestionario completado',
            'progreso': float(estado.progreso),
            'fecha_completado': estado.fecha_completado
        }, status=status.HTTP_400_BAD_REQUEST)
    
    respuestas_data = request.data.get('respuestas', [])
    
    if not respuestas_data:
        return Response({
            'error': 'No se enviaron respuestas'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Procesar respuestas
    with transaction.atomic():
        respuestas_creadas = []
        errores = []
        
        for idx, resp_data in enumerate(respuestas_data):
            try:
                # Validar pregunta
                pregunta_id = resp_data.get('pregunta_id')
                pregunta = get_object_or_404(Pregunta, id=pregunta_id)
                
                # Verificar que pertenece al cuestionario
                if not cuestionario.preguntas.filter(pregunta=pregunta).exists():
                    errores.append({
                        'pregunta_id': pregunta_id,
                        'error': 'Esta pregunta no pertenece al cuestionario'
                    })
                    continue
                
                # Eliminar respuestas previas de esta pregunta
                Respuesta.objects.filter(
                    alumno=alumno,
                    cuestionario=cuestionario,
                    pregunta=pregunta
                ).delete()
                
                # Procesar según tipo
                if pregunta.tipo == 'SELECCION_ALUMNO':
                    seleccionados = resp_data.get('seleccionados', [])
                    
                    if not seleccionados:
                        errores.append({
                            'pregunta_id': pregunta_id,
                            'error': 'Debe seleccionar al menos un compañero'
                        })
                        continue
                    
                    if len(seleccionados) > pregunta.max_elecciones:
                        errores.append({
                            'pregunta_id': pregunta_id,
                            'error': f'Máximo {pregunta.max_elecciones} selecciones'
                        })
                        continue
                    
                    # Crear respuestas
                    for sel in seleccionados:
                        alumno_seleccionado_id = sel.get('alumno_id')
                        orden = sel.get('orden', 1)
                        
                        # Verificar que el seleccionado sea del mismo grupo
                        es_del_grupo = AlumnoGrupo.objects.filter(
                            alumno_id=alumno_seleccionado_id,
                            grupo=alumno_grupo.grupo,
                            activo=True
                        ).exists()
                        
                        if not es_del_grupo:
                            errores.append({
                                'pregunta_id': pregunta_id,
                                'alumno_id': alumno_seleccionado_id,
                                'error': 'El alumno seleccionado no es de tu grupo'
                            })
                            continue
                        
                        # Calcular puntaje
                        puntaje = max(1, pregunta.max_elecciones - orden + 1)
                        
                        respuesta = Respuesta.objects.create(
                            alumno=alumno,
                            cuestionario=cuestionario,
                            pregunta=pregunta,
                            seleccionado_alumno_id=alumno_seleccionado_id,
                            orden_eleccion=orden,
                            puntaje=puntaje
                        )
                        
                        respuestas_creadas.append(respuesta.id)
                
                elif pregunta.tipo == 'OPCION':
                    opcion_id = resp_data.get('opcion_id')
                    
                    if not opcion_id:
                        errores.append({
                            'pregunta_id': pregunta_id,
                            'error': 'Debe seleccionar una opción'
                        })
                        continue
                    
                    respuesta = Respuesta.objects.create(
                        alumno=alumno,
                        cuestionario=cuestionario,
                        pregunta=pregunta,
                        opcion_id=opcion_id
                    )
                    
                    respuestas_creadas.append(respuesta.id)
                
                elif pregunta.tipo == 'TEXTO':
                    texto = resp_data.get('texto_respuesta', '').strip()
                    
                    if not texto:
                        errores.append({
                            'pregunta_id': pregunta_id,
                            'error': 'Debe proporcionar una respuesta'
                        })
                        continue
                    
                    respuesta = Respuesta.objects.create(
                        alumno=alumno,
                        cuestionario=cuestionario,
                        pregunta=pregunta,
                        texto_respuesta=texto
                    )
                    
                    respuestas_creadas.append(respuesta.id)
            
            except Exception as e:
                errores.append({
                    'pregunta_id': resp_data.get('pregunta_id'),
                    'error': str(e)
                })
        
        # Actualizar progreso
        if estado:
            estado.actualizar_progreso()
    
    return Response({
        'success': True,
        'respuestas_guardadas': len(respuestas_creadas),
        'errores': errores if errores else None,
        'progreso': estado.progreso if estado else 0
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_alumno
def mi_progreso_view(request, cuestionario_id):
    """
    Ver progreso personal en el cuestionario
    
    GET /api/student/cuestionarios/{id}/mi-progreso/
    
    Response:
    {
        "cuestionario_id": 1,
        "cuestionario_titulo": "...",
        "grupo_id": 1,
        "grupo_clave": "1A",
        "total_preguntas": 3,
        "preguntas_respondidas": 2,
        "progreso": 66.67,
        "estado": "EN_PROGRESO",
        "fecha_inicio": "...",
        "fecha_completado": null
    }
    """
    alumno = request.alumno
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)
    
    # Obtener grupo del alumno
    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=alumno,
        grupo__periodo=cuestionario.periodo,
        activo=True
    ).select_related('grupo').first()
    
    if not alumno_grupo:
        return Response({
            'error': 'No tienes acceso a este cuestionario'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Obtener estado
    estado = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        alumno=alumno,
        grupo=alumno_grupo.grupo
    ).first()
    
    if not estado:
        return Response({
            'error': 'No se encontró tu registro de progreso'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Contar preguntas respondidas
    total_preguntas = cuestionario.total_preguntas
    preguntas_respondidas = Respuesta.objects.filter(
        alumno=alumno,
        cuestionario=cuestionario
    ).values('pregunta').distinct().count()
    
    return Response({
        'cuestionario_id': cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'grupo_id': alumno_grupo.grupo.id,
        'grupo_clave': alumno_grupo.grupo.clave,
        'total_preguntas': total_preguntas,
        'preguntas_respondidas': preguntas_respondidas,
        'progreso': float(estado.progreso),
        'estado': estado.estado,
        'fecha_inicio': estado.fecha_inicio,
        'fecha_completado': estado.fecha_completado
    }, status=status.HTTP_200_OK)