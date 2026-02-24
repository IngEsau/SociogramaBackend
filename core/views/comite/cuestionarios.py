# core/views/comite/cuestionarios.py
"""
Endpoints para Comité - Analytics y Sociogramas (Solo Lectura)
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Case, When, IntegerField

from core.models import (
    Cuestionario, CuestionarioEstado, Grupo, Respuesta, Periodo,
    AlumnoGrupo
)
from core.serializers import (
    CuestionarioListSerializer,
    CuestionarioDetailSerializer,
)
from core.utils.decorators import require_comite_readonly

# Reutilizar helpers de academic — no duplicar lógica
from core.views.academic.cuestionarios import (
    _calcular_nodos_sociograma,
    _calcular_conexiones_sociograma,
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def listar_cuestionarios_comite_view(request):
    """
    Lista cuestionarios con filtros opcionales.

    GET /api/comite/cuestionarios/

    Query params:
    - periodo_id  : filtrar por periodo específico
    - todos       : "true" para ver todos los periodos históricos
                    Si no se pasa ninguno → periodo activo por default

    Response:
    {
        "periodo": { "id": 1, "codigo": "2026-1", "nombre": "..." },
        "total": 3,
        "cuestionarios": [ ... ]
    }
    """
    periodo_id = request.query_params.get('periodo_id')
    todos = request.query_params.get('todos', 'false').lower() == 'true'

    # Construir queryset base
    qs = Cuestionario.objects.select_related('periodo').order_by('-creado_en')

    periodo_info = None

    if todos:
        # Ver todos los periodos históricos — sin filtro de periodo
        pass

    elif periodo_id:
        # Periodo específico solicitado
        periodo = get_object_or_404(Periodo, id=periodo_id)
        qs = qs.filter(periodo=periodo)
        periodo_info = {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': periodo.activo,
        }

    else:
        # Default: periodo activo — misma lógica que obtener_periodo_activo_view
        try:
            periodo = Periodo.objects.get(activo=1)
        except Periodo.DoesNotExist:
            return Response(
                {'error': 'No hay ningún periodo activo'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Periodo.MultipleObjectsReturned:
            # Si hay múltiples activos, tomar el más reciente (igual que obtener_periodo_activo_view)
            periodo = Periodo.objects.filter(activo=1).order_by('-codigo').first()

        qs = qs.filter(periodo=periodo)
        periodo_info = {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': bool(periodo.activo),
        }

    serializer = CuestionarioListSerializer(qs, many=True)

    return Response({
        'periodo': periodo_info,
        'total': qs.count(),
        'cuestionarios': serializer.data,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def detalle_cuestionario_comite_view(request, cuestionario_id):
    """
    Detalle y previsualización de un cuestionario.
    COMITÉ puede ver cualquier cuestionario sin restricción de grupo.

    GET /api/comite/cuestionarios/{id}/

    Response:
    {
        "cuestionario": { ... }   ← incluye preguntas
    }
    """
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )

    serializer = CuestionarioDetailSerializer(cuestionario)

    return Response({
        'cuestionario': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def progreso_cuestionario_comite_view(request, cuestionario_id):
    """
    Progreso de todos los grupos en un cuestionario.
    COMITÉ ve todos los grupos, con filtros opcionales.

    GET /api/comite/cuestionarios/{id}/progreso/

    Query params (todos opcionales, se pueden combinar):
    - division_id  : filtrar grupos por división
    - programa_id  : filtrar grupos por programa educativo
    - grupo_id     : ver un grupo específico

    Response:
    {
        "cuestionario_id": 1,
        "cuestionario_titulo": "...",
        "filtros_aplicados": { ... },
        "total_grupos": 10,
        "grupos": [
            {
                "grupo_id": 1,
                "grupo_clave": "IDGS-5-A",
                "division": "...",
                "programa": "...",
                "total_alumnos": 25,
                "completados": 20,
                "en_progreso": 3,
                "pendientes": 2,
                "porcentaje_completado": 80.0
            }
        ]
    }
    """
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )

    # Filtros opcionales
    division_id = request.query_params.get('division_id')
    programa_id = request.query_params.get('programa_id')
    grupo_id = request.query_params.get('grupo_id')

    # Base: todos los grupos del periodo del cuestionario
    grupos_qs = Grupo.objects.filter(
        periodo=cuestionario.periodo,
        activo=True
    ).select_related('programa', 'programa__division')

    # Aplicar filtros opcionales
    if division_id:
        grupos_qs = grupos_qs.filter(programa__division_id=division_id)
    if programa_id:
        grupos_qs = grupos_qs.filter(programa_id=programa_id)
    if grupo_id:
        grupos_qs = grupos_qs.filter(id=grupo_id)

    if not grupos_qs.exists():
        return Response({
            'error': 'No se encontraron grupos con los filtros especificados'
        }, status=status.HTTP_404_NOT_FOUND)

    grupos_ids = list(grupos_qs.values_list('id', flat=True))

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

    grupos_data = []
    for grupo in grupos_qs:
        e = estados_por_grupo.get(grupo.id, {
            'total': 0, 'completados': 0, 'en_progreso': 0, 'pendientes': 0
        })
        total = e['total']
        completados = e['completados']
        porcentaje = round(completados / total * 100, 2) if total > 0 else 0

        grupos_data.append({
            'grupo_id': grupo.id,
            'grupo_clave': grupo.clave,
            'division': grupo.programa.division.nombre if grupo.programa and grupo.programa.division else None,
            'programa': grupo.programa.nombre if grupo.programa else None,
            'total_alumnos': total,
            'completados': completados,
            'en_progreso': e['en_progreso'],
            'pendientes': e['pendientes'],
            'porcentaje_completado': porcentaje,
        })

    # Registrar filtros aplicados para transparencia en la respuesta
    filtros_aplicados = {}
    if division_id:
        filtros_aplicados['division_id'] = division_id
    if programa_id:
        filtros_aplicados['programa_id'] = programa_id
    if grupo_id:
        filtros_aplicados['grupo_id'] = grupo_id

    return Response({
        'cuestionario_id': cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'periodo': cuestionario.periodo.codigo,
        'filtros_aplicados': filtros_aplicados,
        'total_grupos': len(grupos_data),
        'grupos': grupos_data,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def estadisticas_cuestionario_comite_view(request, cuestionario_id):
    """
    Estadísticas sociométricas (sociograma) de cualquier grupo.
    COMITÉ ve todos los grupos sin restricción de tutoría.

    GET /api/comite/cuestionarios/{id}/estadisticas/

    Query params (todos opcionales, se pueden combinar):
    - division_id  : filtrar grupos por división
    - programa_id  : filtrar grupos por programa educativo
    - grupo_id     : ver sociograma de un grupo específico

    Response:
    {
        "cuestionario_id": 1,
        "cuestionario_titulo": "...",
        "periodo": "2026-1",
        "filtros_aplicados": { ... },
        "total_grupos": 2,
        "grupos": [
            {
                "grupo_id": 1,
                "grupo_clave": "IDGS-5-A",
                "division": "...",
                "programa": "...",
                "total_alumnos": 25,
                "respuestas_completas": 20,
                "nodos": [ ... ],
                "conexiones": [ ... ]
            }
        ]
    }
    """
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )

    # Filtros opcionales
    division_id = request.query_params.get('division_id')
    programa_id = request.query_params.get('programa_id')
    grupo_id = request.query_params.get('grupo_id')

    # Base: todos los grupos del periodo del cuestionario
    grupos_qs = Grupo.objects.filter(
        periodo=cuestionario.periodo,
        activo=True
    ).select_related('programa', 'programa__division')

    # Aplicar filtros opcionales
    if division_id:
        grupos_qs = grupos_qs.filter(programa__division_id=division_id)
    if programa_id:
        grupos_qs = grupos_qs.filter(programa_id=programa_id)
    if grupo_id:
        grupos_qs = grupos_qs.filter(id=grupo_id)

    if not grupos_qs.exists():
        return Response({
            'error': 'No se encontraron grupos con los filtros especificados'
        }, status=status.HTTP_404_NOT_FOUND)

    # Calcular sociograma por grupo — reutiliza helpers de academic
    grupos_data = []
    for grupo in grupos_qs:
        nodos_data = _calcular_nodos_sociograma(cuestionario, grupo)
        conexiones_data = _calcular_conexiones_sociograma(cuestionario, grupo)

        grupos_data.append({
            'grupo_id': grupo.id,
            'grupo_clave': grupo.clave,
            'division': grupo.programa.division.nombre if grupo.programa and grupo.programa.division else None,
            'programa': grupo.programa.nombre if grupo.programa else None,
            'total_alumnos': nodos_data['total_alumnos'],
            'respuestas_completas': nodos_data['respuestas_completas'],
            'nodos': nodos_data['nodos'],
            'conexiones': conexiones_data,
        })

    filtros_aplicados = {}
    if division_id:
        filtros_aplicados['division_id'] = division_id
    if programa_id:
        filtros_aplicados['programa_id'] = programa_id
    if grupo_id:
        filtros_aplicados['grupo_id'] = grupo_id

    return Response({
        'cuestionario_id': cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'periodo': cuestionario.periodo.codigo,
        'filtros_aplicados': filtros_aplicados,
        'total_grupos': len(grupos_data),
        'grupos': grupos_data,
    }, status=status.HTTP_200_OK)