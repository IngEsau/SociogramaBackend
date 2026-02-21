# core/views/admin/preguntas.py
"""
Endpoints para gestión del banco de preguntas (Admin)
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from core.models import Pregunta, CuestionarioPregunta
from core.serializers import PreguntaSerializer
from core.utils.decorators import require_admin

LIMITE_BANCO = 30


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_admin
def listar_preguntas_view(request):
    """
    Lista todas las preguntas del banco global.

    GET /api/admin/preguntas/

    Query params:
    - tipo: SELECCION_ALUMNO | OPCION | TEXTO (opcional)
    - polaridad: POSITIVA | NEGATIVA (opcional)
    - activa: true | false (opcional)
    """
    preguntas = Pregunta.objects.prefetch_related('opciones').all()

    tipo = request.query_params.get('tipo')
    polaridad = request.query_params.get('polaridad')
    activa = request.query_params.get('activa')

    if tipo:
        preguntas = preguntas.filter(tipo=tipo)

    if polaridad:
        preguntas = preguntas.filter(polaridad=polaridad.upper())

    if activa is not None:
        preguntas = preguntas.filter(activa=activa.lower() == 'true')

    preguntas = preguntas.order_by('orden')
    serializer = PreguntaSerializer(preguntas, many=True)

    return Response({
        'total': preguntas.count(),
        'preguntas': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def crear_pregunta_view(request):
    """
    Crea una o varias preguntas en el banco global.
    Límite máximo: 30 preguntas en el banco.

    Acepta un objeto o un array de objetos.

    POST /api/admin/preguntas/crear/

    --- Una sola pregunta ---
    {
        "texto": "¿Con quién trabajarías?",
        "tipo": "SELECCION_ALUMNO",
        "polaridad": "POSITIVA",
        "max_elecciones": 3,
        "orden": 1,
        "descripcion": "Opcional"
    }

    --- Varias preguntas ---
    [
        { "texto": "...", "tipo": "SELECCION_ALUMNO", "polaridad": "POSITIVA", "max_elecciones": 3, "orden": 1 },
        { "texto": "...", "tipo": "SELECCION_ALUMNO", "polaridad": "NEGATIVA", "max_elecciones": 3, "orden": 2 }
    ]
    """
    data = request.data

    # Detectar si viene un objeto o un array
    es_bulk = isinstance(data, list)
    data_list = data if es_bulk else [data]

    if len(data_list) == 0:
        return Response({
            'success': False,
            'error': 'Debe enviar al menos una pregunta.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validar límite de 30 preguntas en el banco
    total_actual = Pregunta.objects.count()
    if total_actual + len(data_list) > LIMITE_BANCO:
        disponibles = LIMITE_BANCO - total_actual
        return Response({
            'success': False,
            'error': f'El banco no puede tener más de {LIMITE_BANCO} preguntas. '
                     f'Actualmente hay {total_actual}. '
                     f'Solo puedes agregar {disponibles} más.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validar todos antes de guardar cualquiera
    serializers_validos = []
    errores = []

    for i, item in enumerate(data_list):
        serializer = PreguntaSerializer(data=item)
        if serializer.is_valid():
            serializers_validos.append(serializer)
        else:
            errores.append({
                'indice': i,
                'data': item,
                'errores': serializer.errors
            })

    # Si hay cualquier error no guardar nada
    if errores:
        return Response({
            'success': False,
            'message': f'{len(errores)} pregunta(s) con errores. No se guardó ninguna.',
            'errores': errores
        }, status=status.HTTP_400_BAD_REQUEST)

    # Guardar todas
    preguntas_creadas = [s.save() for s in serializers_validos]

    if es_bulk:
        return Response({
            'success': True,
            'total_creadas': len(preguntas_creadas),
            'preguntas': PreguntaSerializer(preguntas_creadas, many=True).data,
            'message': f'{len(preguntas_creadas)} preguntas creadas en el banco correctamente.'
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'success': True,
            'pregunta': PreguntaSerializer(preguntas_creadas[0]).data,
            'message': 'Pregunta creada en el banco correctamente.'
        }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_admin
def detalle_pregunta_view(request, pregunta_id):
    """
    Detalle de una pregunta del banco.

    GET /api/admin/preguntas/<id>/
    """
    pregunta = get_object_or_404(
        Pregunta.objects.prefetch_related('opciones'),
        id=pregunta_id
    )

    serializer = PreguntaSerializer(pregunta)

    return Response({
        'pregunta': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@require_admin
def actualizar_pregunta_view(request, pregunta_id):
    """
    Actualiza una pregunta del banco.

    PUT /api/admin/preguntas/<id>/actualizar/
    """
    pregunta = get_object_or_404(Pregunta, id=pregunta_id)

    if pregunta.respuestas.exists():
        return Response({
            'success': False,
            'error': 'No se puede editar una pregunta que ya tiene respuestas registradas.',
            'respuestas_count': pregunta.respuestas.count()
        }, status=status.HTTP_400_BAD_REQUEST)

    serializer = PreguntaSerializer(pregunta, data=request.data, partial=True)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    pregunta = serializer.save()

    return Response({
        'success': True,
        'pregunta': PreguntaSerializer(pregunta).data
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@require_admin
def eliminar_pregunta_view(request, pregunta_id):
    """
    Elimina una pregunta del banco.

    DELETE /api/admin/preguntas/<id>/eliminar/
    """
    pregunta = get_object_or_404(Pregunta, id=pregunta_id)

    if pregunta.respuestas.exists():
        return Response({
            'success': False,
            'error': 'No se puede eliminar una pregunta que ya tiene respuestas registradas.',
            'respuestas_count': pregunta.respuestas.count()
        }, status=status.HTTP_400_BAD_REQUEST)

    texto = pregunta.texto[:60]
    pregunta.delete()

    return Response({
        'success': True,
        'message': f'Pregunta "{texto}..." eliminada del banco correctamente.'
    }, status=status.HTTP_200_OK)