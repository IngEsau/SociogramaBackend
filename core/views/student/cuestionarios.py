# core/views/student/cuestionarios.py
"""
Endpoints para Estudiantes - Cuestionarios Sociometricos
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

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
    """
    alumno = request.alumno

    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=alumno,
        activo=True,
        grupo__activo=True,
        grupo__periodo__activo=True
    ).select_related('grupo', 'grupo__periodo').first()

    if not alumno_grupo:
        return Response({
            'cuestionarios': [],
            'message': 'No estas inscrito en ningun grupo activo'
        }, status=status.HTTP_200_OK)

    cuestionarios = Cuestionario.objects.filter(
        periodo=alumno_grupo.grupo.periodo,
        activo=True
    ).select_related('periodo').order_by('-creado_en')

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
    Detalle de un cuestionario especifico
    GET /api/student/cuestionarios/{id}/
    """
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )

    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=request.alumno,
        grupo__periodo=cuestionario.periodo,
        activo=True
    ).first()

    if not alumno_grupo:
        return Response({'error': 'No tienes acceso a este cuestionario'}, status=status.HTTP_403_FORBIDDEN)

    if not cuestionario.esta_activo:
        return Response({'error': 'Este cuestionario no esta disponible en este momento'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = CuestionarioDetailSerializer(cuestionario)
    return Response({'cuestionario': serializer.data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_alumno
def preguntas_cuestionario_view(request, cuestionario_id):
    """
    Obtiene preguntas del cuestionario con companeros para seleccionar
    GET /api/student/cuestionarios/{id}/preguntas/
    """
    alumno = request.alumno
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)

    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=alumno,
        grupo__periodo=cuestionario.periodo,
        activo=True
    ).select_related('grupo').first()

    if not alumno_grupo:
        return Response({'error': 'No tienes acceso a este cuestionario'}, status=status.HTTP_403_FORBIDDEN)

    if not cuestionario.esta_activo:
        return Response({'error': 'Este cuestionario no esta disponible'}, status=status.HTTP_400_BAD_REQUEST)

    preguntas_cuestionario = cuestionario.preguntas.select_related('pregunta').order_by('orden')

    preguntas_data = []
    for cp in preguntas_cuestionario:
        pregunta = cp.pregunta
        ya_respondio = Respuesta.objects.filter(
            alumno=alumno, cuestionario=cuestionario, pregunta=pregunta
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

    companeros = AlumnoGrupo.objects.filter(
        grupo=alumno_grupo.grupo,
        activo=True
    ).exclude(alumno=alumno).select_related('alumno', 'alumno__user').order_by('alumno__user__nombre_completo')

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
    Guarda respuestas del cuestionario.
    Para preguntas SELECCION_ALUMNO se deben enviar EXACTAMENTE
    max_elecciones selecciones — ni mas ni menos.

    POST /api/student/cuestionarios/{id}/responder/

    Body:
    {
        "respuestas": [
            {
                "pregunta_id": 32,
                "seleccionados": [
                    {"alumno_id": 5, "orden": 1},
                    {"alumno_id": 8, "orden": 2},
                    {"alumno_id": 12, "orden": 3}
                ]
            }
        ]
    }

    Validaciones server-side:
    - No autovoto: destino_id != alumno_actual.id
    - Pertenencia al grupo: todos los destinos son del mismo grupo activo
    - Limite exacto: exactamente max_elecciones selecciones
    - Ventana de tiempo: cuestionario activo + periodo activo
    - Sin duplicados: no se puede votar dos veces al mismo destino en la misma pregunta
    - Atomico: o se guarda todo o nada
    """
    alumno = request.alumno
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )

    # ── Validacion 1: periodo activo ──────────────────────────────────────
    if not cuestionario.periodo.activo:
        return Response({
            'error': 'El periodo de este cuestionario no esta activo'
        }, status=status.HTTP_400_BAD_REQUEST)

    # ── Validacion 2: ventana de tiempo del cuestionario ─────────────────
    if not cuestionario.esta_activo:
        return Response({
            'error': 'Este cuestionario no esta disponible en este momento'
        }, status=status.HTTP_400_BAD_REQUEST)

    # ── Validacion 3: alumno pertenece al grupo del periodo ───────────────
    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=alumno,
        grupo__periodo=cuestionario.periodo,
        activo=True
    ).select_related('grupo').first()

    if not alumno_grupo:
        return Response({
            'error': 'No tienes acceso a este cuestionario'
        }, status=status.HTTP_403_FORBIDDEN)

    # ── Validacion 4: no haber completado ya el cuestionario ─────────────
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

    # ── Pre-validacion de todo el payload antes de tocar la BD ───────────
    # Obtener IDs validos del grupo (en batch — sin N+1)
    alumnos_grupo_ids = set(
        AlumnoGrupo.objects.filter(
            grupo=alumno_grupo.grupo,
            activo=True
        ).exclude(alumno=alumno).values_list('alumno_id', flat=True)
    )

    # Obtener preguntas del cuestionario en batch
    preguntas_cuestionario = {
        cp.pregunta_id: cp.pregunta
        for cp in cuestionario.preguntas.select_related('pregunta')
    }

    errores_validacion = []

    for resp_data in respuestas_data:
        pregunta_id = resp_data.get('pregunta_id')

        # Pregunta existe y pertenece al cuestionario
        if pregunta_id not in preguntas_cuestionario:
            errores_validacion.append({
                'pregunta_id': pregunta_id,
                'error': 'Esta pregunta no pertenece al cuestionario'
            })
            continue

        pregunta = preguntas_cuestionario[pregunta_id]

        if pregunta.tipo == 'SELECCION_ALUMNO':
            seleccionados = resp_data.get('seleccionados', [])

            # Validacion: exactamente max_elecciones
            if len(seleccionados) != pregunta.max_elecciones:
                errores_validacion.append({
                    'pregunta_id': pregunta_id,
                    'error': (
                        f'Debes seleccionar exactamente {pregunta.max_elecciones} '
                        f'companero(s). Enviaste {len(seleccionados)}.'
                    )
                })
                continue

            alumno_ids_enviados = [sel.get('alumno_id') for sel in seleccionados]
            ordenes_enviados = [sel.get('orden') for sel in seleccionados]

            # Validacion: no autovoto
            if alumno.id in alumno_ids_enviados:
                errores_validacion.append({
                    'pregunta_id': pregunta_id,
                    'error': 'No puedes votarte a ti mismo'
                })
                continue

            # Validacion: todos los destinos pertenecen al grupo
            ids_fuera_de_grupo = set(alumno_ids_enviados) - alumnos_grupo_ids
            if ids_fuera_de_grupo:
                errores_validacion.append({
                    'pregunta_id': pregunta_id,
                    'error': f'Los siguientes alumnos no pertenecen a tu grupo: {list(ids_fuera_de_grupo)}'
                })
                continue

            # Validacion: sin duplicados en destinos
            if len(alumno_ids_enviados) != len(set(alumno_ids_enviados)):
                errores_validacion.append({
                    'pregunta_id': pregunta_id,
                    'error': 'No puedes seleccionar al mismo companero dos veces en la misma pregunta'
                })
                continue

            # Validacion: ordenes unicos
            if len(ordenes_enviados) != len(set(ordenes_enviados)):
                errores_validacion.append({
                    'pregunta_id': pregunta_id,
                    'error': 'No puedes asignar el mismo orden a dos companeros distintos'
                })
                continue

        elif pregunta.tipo == 'OPCION':
            if not resp_data.get('opcion_id'):
                errores_validacion.append({
                    'pregunta_id': pregunta_id,
                    'error': 'Debe seleccionar una opcion'
                })

        elif pregunta.tipo == 'TEXTO':
            if not resp_data.get('texto_respuesta', '').strip():
                errores_validacion.append({
                    'pregunta_id': pregunta_id,
                    'error': 'Debe proporcionar una respuesta de texto'
                })

    # Si hay cualquier error de validacion — no se guarda nada
    if errores_validacion:
        return Response({
            'success': False,
            'error': 'El envio contiene errores de validacion. No se guardo ninguna respuesta.',
            'errores': errores_validacion
        }, status=status.HTTP_400_BAD_REQUEST)

    # ── Guardar — todo o nada ─────────────────────────────────────────────
    with transaction.atomic():
        respuestas_creadas = []

        for resp_data in respuestas_data:
            pregunta_id = resp_data.get('pregunta_id')
            pregunta = preguntas_cuestionario[pregunta_id]

            # Eliminar respuestas previas de esta pregunta (permite re-envio parcial)
            Respuesta.objects.filter(
                alumno=alumno,
                cuestionario=cuestionario,
                pregunta=pregunta
            ).delete()

            if pregunta.tipo == 'SELECCION_ALUMNO':
                seleccionados = resp_data.get('seleccionados', [])
                nuevas = []
                for sel in seleccionados:
                    orden = sel.get('orden', 1)
                    puntaje = max(1, pregunta.max_elecciones - orden + 1)
                    nuevas.append(Respuesta(
                        alumno=alumno,
                        cuestionario=cuestionario,
                        pregunta=pregunta,
                        seleccionado_alumno_id=sel.get('alumno_id'),
                        orden_eleccion=orden,
                        puntaje=puntaje
                    ))
                creadas = Respuesta.objects.bulk_create(nuevas)
                respuestas_creadas.extend([r.id for r in creadas])

            elif pregunta.tipo == 'OPCION':
                respuesta = Respuesta.objects.create(
                    alumno=alumno, cuestionario=cuestionario,
                    pregunta=pregunta, opcion_id=resp_data.get('opcion_id')
                )
                respuestas_creadas.append(respuesta.id)

            elif pregunta.tipo == 'TEXTO':
                respuesta = Respuesta.objects.create(
                    alumno=alumno, cuestionario=cuestionario,
                    pregunta=pregunta,
                    texto_respuesta=resp_data.get('texto_respuesta', '').strip()
                )
                respuestas_creadas.append(respuesta.id)

        if estado:
            estado.actualizar_progreso()

    return Response({
        'success': True,
        'respuestas_guardadas': len(respuestas_creadas),
        'progreso': float(estado.progreso) if estado else 0
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_alumno
def mi_progreso_view(request, cuestionario_id):
    """
    Ver progreso personal en el cuestionario
    GET /api/student/cuestionarios/{id}/mi-progreso/
    """
    alumno = request.alumno
    cuestionario = get_object_or_404(Cuestionario, id=cuestionario_id)

    alumno_grupo = AlumnoGrupo.objects.filter(
        alumno=alumno,
        grupo__periodo=cuestionario.periodo,
        activo=True
    ).select_related('grupo').first()

    if not alumno_grupo:
        return Response({'error': 'No tienes acceso a este cuestionario'}, status=status.HTTP_403_FORBIDDEN)

    estado = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        alumno=alumno,
        grupo=alumno_grupo.grupo
    ).first()

    if not estado:
        return Response({'error': 'No se encontro tu registro de progreso'}, status=status.HTTP_404_NOT_FOUND)

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