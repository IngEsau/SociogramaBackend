# core/views/comite/cuestionarios.py
"""
Endpoints para Comité - Analytics y Sociogramas (Solo Lectura)
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Case, When, IntegerField

from core.models import (
    Cuestionario, CuestionarioEstado, Grupo, Periodo, AlumnoGrupo
)
from core.serializers import (
    CuestionarioListSerializer,
    CuestionarioDetailSerializer,
)
from core.utils.decorators import require_comite_readonly
from core.views.comite.helpers import (
    _calcular_nodos_batch,
    _calcular_conexiones_batch,
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
                    Sin parámetros → periodo activo por default

    Response:
    {
        "periodo": { "id", "codigo", "nombre", "activo" },
        "total": 3,
        "cuestionarios": [ ... ]
    }
    """
    periodo_id = request.query_params.get('periodo_id')
    todos = request.query_params.get('todos', 'false').lower() == 'true'

    qs = Cuestionario.objects.select_related('periodo').order_by('-creado_en')
    periodo_info = None

    if todos:
        pass  # sin filtro de periodo

    elif periodo_id:
        periodo = get_object_or_404(Periodo, id=periodo_id)
        qs = qs.filter(periodo=periodo)
        periodo_info = {
            'id':     periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': periodo.activo,
        }

    else:
        try:
            periodo = Periodo.objects.get(activo=1)
        except Periodo.DoesNotExist:
            return Response(
                {'error': 'No hay ningún periodo activo'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Periodo.MultipleObjectsReturned:
            periodo = Periodo.objects.filter(activo=1).order_by('-codigo').first()

        qs = qs.filter(periodo=periodo)
        periodo_info = {
            'id':     periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': bool(periodo.activo),
        }

    serializer = CuestionarioListSerializer(qs, many=True)

    return Response({
        'periodo':       periodo_info,
        'total':         qs.count(),
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

    Query params (todos opcionales):
    - division_id, programa_id, grupo_id

    Response:
    {
        "cuestionario_id", "cuestionario_titulo", "periodo",
        "filtros_aplicados", "total_grupos",
        "grupos": [ { "grupo_id", "grupo_clave", "division", "programa",
                      "total_alumnos", "completados", "en_progreso",
                      "pendientes", "porcentaje_completado" } ]
    }
    """
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )

    division_id = request.query_params.get('division_id')
    programa_id = request.query_params.get('programa_id')
    grupo_id    = request.query_params.get('grupo_id')

    grupos_qs = Grupo.objects.filter(
        periodo=cuestionario.periodo,
        activo=True
    ).select_related('programa', 'programa__division')

    if division_id:
        grupos_qs = grupos_qs.filter(programa__division_id=division_id)
    if programa_id:
        grupos_qs = grupos_qs.filter(programa_id=programa_id)
    if grupo_id:
        grupos_qs = grupos_qs.filter(id=grupo_id)

    if not grupos_qs.exists():
        return Response(
            {'error': 'No se encontraron grupos con los filtros especificados'},
            status=status.HTTP_404_NOT_FOUND
        )

    grupos_ids = list(grupos_qs.values_list('id', flat=True))

    # 1 query para todos los estados
    estados_agg = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        grupo_id__in=grupos_ids
    ).values('grupo_id').annotate(
        total=Count('id'),
        completados=Count(Case(When(estado='COMPLETADO', then=1), output_field=IntegerField())),
        en_progreso=Count(Case(When(estado='EN_PROGRESO', then=1), output_field=IntegerField())),
        pendientes=Count(Case(When(estado='PENDIENTE',   then=1), output_field=IntegerField())),
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
            'grupo_id':              grupo.id,
            'grupo_clave':           grupo.clave,
            'division':              grupo.programa.division.nombre if grupo.programa and grupo.programa.division else None,
            'programa':              grupo.programa.nombre if grupo.programa else None,
            'total_alumnos':         total,
            'completados':           completados,
            'en_progreso':           e['en_progreso'],
            'pendientes':            e['pendientes'],
            'porcentaje_completado': porcentaje,
        })

    filtros_aplicados = {}
    if division_id:
        filtros_aplicados['division_id'] = division_id
    if programa_id:
        filtros_aplicados['programa_id'] = programa_id
    if grupo_id:
        filtros_aplicados['grupo_id'] = grupo_id

    return Response({
        'cuestionario_id':     cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'periodo':             cuestionario.periodo.codigo,
        'filtros_aplicados':   filtros_aplicados,
        'total_grupos':        len(grupos_data),
        'grupos':              grupos_data,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def estadisticas_cuestionario_comite_view(request, cuestionario_id):
    """
    Estadísticas sociométricas (sociograma) de cualquier grupo.
    COMITÉ ve todos los grupos sin restricción de tutoría.

    GET /api/comite/cuestionarios/{id}/estadisticas/

    Query params (todos opcionales):
    - division_id, programa_id, grupo_id

    Response:
    {
        "cuestionario_id", "cuestionario_titulo", "periodo",
        "filtros_aplicados", "total_grupos",
        "grupos": [ { "grupo_id", "grupo_clave", "division", "programa",
                      "total_alumnos", "respuestas_completas",
                      "nodos": [...], "conexiones": [...] } ]
    }
    """
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('periodo'),
        id=cuestionario_id
    )

    division_id = request.query_params.get('division_id')
    programa_id = request.query_params.get('programa_id')
    grupo_id    = request.query_params.get('grupo_id')

    grupos_qs = Grupo.objects.filter(
        periodo=cuestionario.periodo,
        activo=True
    ).select_related('programa', 'programa__division')

    if division_id:
        grupos_qs = grupos_qs.filter(programa__division_id=division_id)
    if programa_id:
        grupos_qs = grupos_qs.filter(programa_id=programa_id)
    if grupo_id:
        grupos_qs = grupos_qs.filter(id=grupo_id)

    if not grupos_qs.exists():
        return Response(
            {'error': 'No se encontraron grupos con los filtros especificados'},
            status=status.HTTP_404_NOT_FOUND
        )

    grupos_list = list(grupos_qs)

    # Batch: ~9 queries fijas para todos los grupos
    nodos_por_grupo      = _calcular_nodos_batch(cuestionario, grupos_list)
    conexiones_por_grupo = _calcular_conexiones_batch(cuestionario, grupos_list)

    grupos_data = []
    for grupo in grupos_list:
        gid        = grupo.id
        nodos_data = nodos_por_grupo.get(gid, {
            'nodos': [], 'total_alumnos': 0, 'respuestas_completas': 0
        })

        grupos_data.append({
            'grupo_id':             gid,
            'grupo_clave':          grupo.clave,
            'division':             grupo.programa.division.nombre if grupo.programa and grupo.programa.division else None,
            'programa':             grupo.programa.nombre if grupo.programa else None,
            'total_alumnos':        nodos_data['total_alumnos'],
            'respuestas_completas': nodos_data['respuestas_completas'],
            'nodos':                nodos_data['nodos'],
            'conexiones':           conexiones_por_grupo.get(gid, []),
        })

    filtros_aplicados = {}
    if division_id:
        filtros_aplicados['division_id'] = division_id
    if programa_id:
        filtros_aplicados['programa_id'] = programa_id
    if grupo_id:
        filtros_aplicados['grupo_id'] = grupo_id

    return Response({
        'cuestionario_id':     cuestionario.id,
        'cuestionario_titulo': cuestionario.titulo,
        'periodo':             cuestionario.periodo.codigo,
        'filtros_aplicados':   filtros_aplicados,
        'total_grupos':        len(grupos_data),
        'grupos':              grupos_data,
    }, status=status.HTTP_200_OK)