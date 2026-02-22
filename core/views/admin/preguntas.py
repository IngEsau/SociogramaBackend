# core/views/admin/preguntas.py
"""
Endpoints para gestión del banco de preguntas (Admin)
ACTUALIZADO: filtro por es_copia=False para banco limpio
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
    Lista las preguntas del banco global (excluye copias de cuestionarios).

    GET /api/admin/preguntas/

    Query params:
    - tipo: SELECCION_ALUMNO | OPCION | TEXTO (opcional)
    - polaridad: POSITIVA | NEGATIVA (opcional)
    - activa: true | false (opcional)
    """
    # Solo preguntas originales del banco — excluir copias creadas al clonar
    preguntas = Pregunta.objects.prefetch_related('opciones').filter(es_copia=False)

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
    Crea pares de preguntas (positiva + negativa) en el banco global.
    Siempre se deben enviar en pares. Acepta uno o varios pares.
    Límite máximo: 30 preguntas en el banco (no cuenta copias).

    POST /api/admin/preguntas/crear/

    --- Un solo par ---
    {
        "positiva": {
            "texto": "¿Con quién trabajarías en equipo?",
            "tipo": "SELECCION_ALUMNO",
            "max_elecciones": 3,
            "orden": 1,
            "descripcion": "Opcional"
        },
        "negativa": {
            "texto": "¿Con quién NO trabajarías en equipo?",
            "tipo": "SELECCION_ALUMNO",
            "max_elecciones": 3,
            "orden": 2,
            "descripcion": "Opcional"
        }
    }

    --- Varios pares ---
    [
        {
            "positiva": { "texto": "...", "tipo": "SELECCION_ALUMNO", "max_elecciones": 3, "orden": 1 },
            "negativa": { "texto": "...", "tipo": "SELECCION_ALUMNO", "max_elecciones": 3, "orden": 2 }
        },
        {
            "positiva": { "texto": "...", "tipo": "SELECCION_ALUMNO", "max_elecciones": 3, "orden": 3 },
            "negativa": { "texto": "...", "tipo": "SELECCION_ALUMNO", "max_elecciones": 3, "orden": 4 }
        }
    ]
    """
    from django.db import transaction

    data = request.data
    es_bulk = isinstance(data, list)
    pares = data if es_bulk else [data]

    if len(pares) == 0:
        return Response({
            'success': False,
            'error': 'Debe enviar al menos un par de preguntas.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validar que cada elemento tenga positiva y negativa
    errores_estructura = []
    for i, par in enumerate(pares):
        if 'positiva' not in par or 'negativa' not in par:
            errores_estructura.append({
                'indice': i,
                'error': 'Cada par debe tener los campos "positiva" y "negativa".'
            })

    if errores_estructura:
        return Response({
            'success': False,
            'error': 'Estructura de pares incorrecta.',
            'detalles': errores_estructura
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verificar límite del banco (cada par agrega 2 preguntas)
    total_actual = Pregunta.objects.filter(es_copia=False).count()
    total_nuevas = len(pares) * 2
    if total_actual + total_nuevas > LIMITE_BANCO:
        disponibles = (LIMITE_BANCO - total_actual) // 2
        return Response({
            'success': False,
            'error': f'El banco no puede tener más de {LIMITE_BANCO} preguntas. '
                     f'Actualmente hay {total_actual}. '
                     f'Solo puedes agregar {disponibles} par(es) más.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Validar todos los serializers antes de guardar
    pares_validos = []
    errores_validacion = []

    for i, par in enumerate(pares):
        # Forzar polaridad correcta
        par['positiva']['polaridad'] = 'POSITIVA'
        par['negativa']['polaridad'] = 'NEGATIVA'

        serializer_pos = PreguntaSerializer(data=par['positiva'])
        serializer_neg = PreguntaSerializer(data=par['negativa'])

        errores_par = {}
        if not serializer_pos.is_valid():
            errores_par['positiva'] = serializer_pos.errors
        if not serializer_neg.is_valid():
            errores_par['negativa'] = serializer_neg.errors

        if errores_par:
            errores_validacion.append({'indice': i, 'errores': errores_par})
        else:
            pares_validos.append((serializer_pos, serializer_neg))

    if errores_validacion:
        return Response({
            'success': False,
            'message': f'{len(errores_validacion)} par(es) con errores. No se guardó ninguno.',
            'errores': errores_validacion
        }, status=status.HTTP_400_BAD_REQUEST)

    # Guardar todos los pares en una sola transacción atómica
    pares_creados = []
    with transaction.atomic():
        for serializer_pos, serializer_neg in pares_validos:
            pregunta_pos = serializer_pos.save()
            pregunta_pos.es_copia = False
            pregunta_pos.save()

            pregunta_neg = serializer_neg.save()
            pregunta_neg.es_copia = False
            pregunta_neg.save()

            # Enlazar el par mutuamente
            pregunta_pos.par_pregunta = pregunta_neg
            pregunta_pos.save()
            pregunta_neg.par_pregunta = pregunta_pos
            pregunta_neg.save()

            pares_creados.append({
                'positiva': PreguntaSerializer(pregunta_pos).data,
                'negativa': PreguntaSerializer(pregunta_neg).data,
            })

    return Response({
        'success': True,
        'total_pares_creados': len(pares_creados),
        'pares': pares_creados,
        'message': f'{len(pares_creados)} par(es) de preguntas creados correctamente.'
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
        id=pregunta_id,
        es_copia=False
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
    Actualiza una pregunta del banco de forma individual.
    No se permite cambiar la polaridad (rompería el equilibrio del par).

    PUT /api/admin/preguntas/<id>/actualizar/
    """
    pregunta = get_object_or_404(Pregunta, id=pregunta_id, es_copia=False)

    if pregunta.respuestas.exists():
        return Response({
            'success': False,
            'error': 'No se puede editar una pregunta que ya tiene respuestas registradas.',
            'respuestas_count': pregunta.respuestas.count()
        }, status=status.HTTP_400_BAD_REQUEST)

    # Bloquear cambio de polaridad
    if 'polaridad' in request.data and request.data['polaridad'] != pregunta.polaridad:
        return Response({
            'success': False,
            'error': 'No se puede cambiar la polaridad de una pregunta. '
                     'Cada pregunta debe mantener su polaridad original para conservar el equilibrio del par.'
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
    Elimina una pregunta del banco junto con su par (positiva <-> negativa).
    Si la pregunta tiene par, ambas se eliminan en una sola transacción atómica.

    DELETE /api/admin/preguntas/<id>/eliminar/

    Response preview (GET antes de confirmar):
    {
        "pregunta_a_eliminar": { id, texto, polaridad },
        "par_a_eliminar": { id, texto, polaridad } | null
    }
    """
    from django.db import transaction

    pregunta = get_object_or_404(Pregunta, id=pregunta_id, es_copia=False)

    # Verificar respuestas en la pregunta principal
    if pregunta.respuestas.exists():
        return Response({
            'success': False,
            'error': 'No se puede eliminar una pregunta que ya tiene respuestas registradas.',
            'respuestas_count': pregunta.respuestas.count()
        }, status=status.HTTP_400_BAD_REQUEST)

    # Buscar su par
    par = pregunta.par_pregunta

    # Verificar respuestas en el par también
    if par and par.respuestas.exists():
        return Response({
            'success': False,
            'error': 'No se puede eliminar el par porque ya tiene respuestas registradas.',
            'respuestas_count': par.respuestas.count()
        }, status=status.HTTP_400_BAD_REQUEST)

    # Datos para la respuesta antes de eliminar
    info_pregunta = {
        'id': pregunta.id,
        'texto': pregunta.texto,
        'polaridad': pregunta.polaridad
    }
    info_par = {
        'id': par.id,
        'texto': par.texto,
        'polaridad': par.polaridad
    } if par else None

    with transaction.atomic():
        if par:
            par.delete()
        pregunta.delete()

    return Response({
        'success': True,
        'eliminadas': {
            'pregunta': info_pregunta,
            'par': info_par
        },
        'message': f'Pregunta y su par eliminadas correctamente.' if info_par else f'Pregunta eliminada correctamente (no tenía par).'
    }, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
@require_admin
def editar_copia_view(request, pregunta_id):
    """
    Edita una pregunta que es copia (asociada a un cuestionario).
    No opera sobre preguntas originales del banco.

    PUT /api/admin/preguntas/<id>/editar-copia/

    Body (campos opcionales):
    {
        "texto": "...",
        "polaridad": "POSITIVA",
        "max_elecciones": 3,
        "descripcion": "..."
    }
    """
    pregunta = get_object_or_404(Pregunta, id=pregunta_id, es_copia=True)

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