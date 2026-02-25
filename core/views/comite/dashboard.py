# core/views/comite/dashboard.py
"""
Endpoints para Comité - Dashboard Global (Solo Lectura)
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Case, When, IntegerField, Q

from core.models import (
    Cuestionario, CuestionarioEstado, Grupo, Respuesta,
    Periodo, AlumnoGrupo
)
from core.utils.decorators import require_comite_readonly
from core.views.academic.cuestionarios import _clasificar_alumno
from core.views.comite.helpers import _calcular_nodos_batch

# ============================================================
# HELPER: resolver cuestionario (sin cambios)
# ============================================================

def _resolver_cuestionario(periodo_id=None, cuestionario_id=None):
    """
    Resuelve qué cuestionario usar según los parámetros.
    Retorna: (cuestionario, periodo, error_response)
    """
    if cuestionario_id:
        cuestionario = Cuestionario.objects.select_related('periodo').filter(
            id=cuestionario_id
        ).first()
        if not cuestionario:
            return None, None, Response(
                {'error': f'Cuestionario {cuestionario_id} no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        return cuestionario, cuestionario.periodo, None

    if periodo_id:
        periodo = Periodo.objects.filter(id=periodo_id).first()
        if not periodo:
            return None, None, Response(
                {'error': f'Periodo {periodo_id} no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
    else:
        try:
            periodo = Periodo.objects.get(activo=1)
        except Periodo.DoesNotExist:
            return None, None, Response(
                {'error': 'No hay ningún periodo activo'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Periodo.MultipleObjectsReturned:
            periodo = Periodo.objects.filter(activo=1).order_by('-codigo').first()

    cuestionario = Cuestionario.objects.select_related('periodo').filter(
        periodo=periodo,
        activo=True
    ).first()

    if not cuestionario:
        return None, None, Response(
            {
                'error': 'No hay cuestionario activo en este periodo',
                'periodo': periodo.codigo
            },
            status=status.HTTP_404_NOT_FOUND
        )

    return cuestionario, periodo, None


def _aplicar_filtros_grupos(grupos_qs, division_id=None, tutor_id=None, grupo_id=None):
    """Aplica filtros opcionales a un queryset de grupos."""
    if division_id:
        grupos_qs = grupos_qs.filter(programa__division_id=division_id)
    if tutor_id:
        grupos_qs = grupos_qs.filter(tutor_id=tutor_id)
    if grupo_id:
        grupos_qs = grupos_qs.filter(id=grupo_id)
    return grupos_qs


def _build_filtros_aplicados(division_id, tutor_id, grupo_id, periodo_id, cuestionario_id):
    """Construye el dict de filtros aplicados."""
    filtros = {}
    if division_id:
        filtros['division_id'] = division_id
    if tutor_id:
        filtros['tutor_id'] = tutor_id
    if grupo_id:
        filtros['grupo_id'] = grupo_id
    if periodo_id:
        filtros['periodo_id'] = periodo_id
    if cuestionario_id:
        filtros['cuestionario_id'] = cuestionario_id
    return filtros

# ============================================================
# VISTAS
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def overview_comite_view(request):
    """
    Resumen ejecutivo global para el Comité.
    GET /api/comite/overview

    Query params (todos opcionales):
    - periodo_id, cuestionario_id, division_id, tutor_id, grupo_id

    Response:
    {
        "cuestionario": { "id", "titulo", "activo" },
        "periodo": { "id", "codigo", "nombre" },
        "filtros_aplicados": {},
        "total_grupos": 45,
        "porcentaje_completado_global": 72.5,
        "alertas_aislados": {
            "total_global": 12,
            "por_division": [ { "division_id", "division", "total_aislados" } ],
            "por_grupo": [ { "grupo_id", "grupo_clave", "division", "total_aislados" } ]
        },
        "top_centralidad": {
            "por_division": [ { "division_id", "division", "top": [...] } ],
            "por_grupo": [ { "grupo_id", "grupo_clave", "top": [...] } ]
        }
    }
    """
    periodo_id      = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id     = request.query_params.get('division_id')
    tutor_id        = request.query_params.get('tutor_id')
    grupo_id        = request.query_params.get('grupo_id')

    cuestionario, periodo, error = _resolver_cuestionario(periodo_id, cuestionario_id)
    if error:
        return error

    grupos_qs = Grupo.objects.filter(
        periodo=periodo,
        activo=True
    ).select_related('programa', 'programa__division', 'tutor', 'tutor__user')
    grupos_qs = _aplicar_filtros_grupos(grupos_qs, division_id, tutor_id, grupo_id)

    if not grupos_qs.exists():
        return Response(
            {'error': 'No se encontraron grupos con los filtros especificados'},
            status=status.HTTP_404_NOT_FOUND
        )

    grupos_list = list(grupos_qs)
    grupos_ids  = [g.id for g in grupos_list]

    # ── Porcentaje completado global ── 1 query ──────────────────────────────
    estados_agg = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        grupo_id__in=grupos_ids
    ).aggregate(
        total=Count('id'),
        completados=Count(Case(When(estado='COMPLETADO', then=1), output_field=IntegerField()))
    )
    total_estados    = estados_agg['total'] or 0
    total_completados = estados_agg['completados'] or 0
    porcentaje_global = round(total_completados / total_estados * 100, 2) if total_estados > 0 else 0

    # ── Nodos en batch ── ~6 queries totales ────────────────────────────────
    nodos_por_grupo = _calcular_nodos_batch(cuestionario, grupos_list)
    # ── Construir alertas y centralidad en memoria ────────────────────────
    alertas_por_grupo  = []
    alertas_por_division = {}
    total_aislados_global = 0

    # Para centralidad: acumular alumnos con su puntos_positivos por división y grupo
    top_por_division = {}  # division_id → { division_id, division, alumnos: [] }
    top_por_grupo_dict = {}  # grupo_id → { grupo_id, grupo_clave, alumnos: [] }

    for grupo in grupos_list:
        gid   = grupo.id
        datos = nodos_por_grupo.get(gid, {'nodos': [], 'total_alumnos': 0, 'respuestas_completas': 0})
        nodos = datos['nodos']

        division_nombre = grupo.programa.division.nombre if grupo.programa and grupo.programa.division else 'Sin división'
        division_id_val = grupo.programa.division.id    if grupo.programa and grupo.programa.division else None

        # Alertas
        aislados = [n for n in nodos if n['tipo'] == 'INVISIBLE']
        if aislados:
            alertas_por_grupo.append({
                'grupo_id':       gid,
                'grupo_clave':    grupo.clave,
                'division':       division_nombre,
                'total_aislados': len(aislados),
            })
            total_aislados_global += len(aislados)

            key = division_id_val
            if key not in alertas_por_division:
                alertas_por_division[key] = {
                    'division_id':    division_id_val,
                    'division':       division_nombre,
                    'total_aislados': 0
                }
            alertas_por_division[key]['total_aislados'] += len(aislados)

        # Centralidad — acumular por división
        if division_id_val not in top_por_division:
            top_por_division[division_id_val] = {
                'division_id': division_id_val,
                'division':    division_nombre,
                'alumnos':     []
            }
        # Centralidad — acumular por grupo
        if gid not in top_por_grupo_dict:
            top_por_grupo_dict[gid] = {
                'grupo_id':    gid,
                'grupo_clave': grupo.clave,
                'alumnos':     []
            }

        for nodo in nodos:
            entrada = {
                'alumno_id':           nodo['alumno_id'],
                'nombre':              nodo['nombre'],
                'matricula':           nodo['matricula'],
                'elecciones_positivas': nodo['puntos_positivos'],
                'grupo_clave':         grupo.clave,
            }
            top_por_division[division_id_val]['alumnos'].append(entrada)
            top_por_grupo_dict[gid]['alumnos'].append(entrada)

    # Top 10 por división
    top_centralidad_division = []
    for div_data in top_por_division.values():
        top_10 = sorted(div_data['alumnos'], key=lambda x: x['elecciones_positivas'], reverse=True)[:10]
        top_centralidad_division.append({
            'division_id': div_data['division_id'],
            'division':    div_data['division'],
            'top': [
                {
                    'alumno_id':           a['alumno_id'],
                    'nombre':              a['nombre'],
                    'matricula':           a['matricula'],
                    'elecciones_positivas': a['elecciones_positivas'],
                    'grupo':               a['grupo_clave'],
                }
                for a in top_10
            ]
        })

    # Top 10 por grupo
    top_centralidad_grupo = []
    for grp_data in top_por_grupo_dict.values():
        top_10 = sorted(grp_data['alumnos'], key=lambda x: x['elecciones_positivas'], reverse=True)[:10]
        top_centralidad_grupo.append({
            'grupo_id':    grp_data['grupo_id'],
            'grupo_clave': grp_data['grupo_clave'],
            'top': [
                {
                    'alumno_id':           a['alumno_id'],
                    'nombre':              a['nombre'],
                    'matricula':           a['matricula'],
                    'elecciones_positivas': a['elecciones_positivas'],
                }
                for a in top_10
            ]
        })

    return Response({
        'cuestionario': {
            'id':     cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id':     periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados':          _build_filtros_aplicados(division_id, tutor_id, grupo_id, periodo_id, cuestionario_id),
        'total_grupos':               len(grupos_ids),
        'porcentaje_completado_global': porcentaje_global,
        'alertas_aislados': {
            'total_global':  total_aislados_global,
            'por_division':  list(alertas_por_division.values()),
            'por_grupo':     alertas_por_grupo,
        },
        'top_centralidad': {
            'por_division': top_centralidad_division,
            'por_grupo':    top_centralidad_grupo,
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def progreso_overview_comite_view(request):
    """
    Porcentaje de completado global del cuestionario.
    GET /api/comite/overview/progreso/

    Query params (todos opcionales):
    - periodo_id, cuestionario_id, division_id, tutor_id, grupo_id

    Response:
    {
        "cuestionario": { "id", "titulo", "activo" },
        "periodo": { "id", "codigo", "nombre" },
        "filtros_aplicados": {},
        "total_grupos": 45,
        "total_alumnos": 1200,
        "total_completados": 870,
        "porcentaje_completado_global": 72.5
    }
    """
    periodo_id      = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id     = request.query_params.get('division_id')
    tutor_id        = request.query_params.get('tutor_id')
    grupo_id        = request.query_params.get('grupo_id')

    cuestionario, periodo, error = _resolver_cuestionario(periodo_id, cuestionario_id)
    if error:
        return error

    grupos_qs = Grupo.objects.filter(
        periodo=periodo,
        activo=True
    ).select_related('programa', 'programa__division')
    grupos_qs = _aplicar_filtros_grupos(grupos_qs, division_id, tutor_id, grupo_id)

    if not grupos_qs.exists():
        return Response(
            {'error': 'No se encontraron grupos con los filtros especificados'},
            status=status.HTTP_404_NOT_FOUND
        )

    grupos_ids = list(grupos_qs.values_list('id', flat=True))

    # 1 query
    estados_agg = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        grupo_id__in=grupos_ids
    ).aggregate(
        total=Count('id'),
        completados=Count(Case(When(estado='COMPLETADO', then=1), output_field=IntegerField()))
    )

    total      = estados_agg['total'] or 0
    completados = estados_agg['completados'] or 0
    porcentaje = round(completados / total * 100, 2) if total > 0 else 0

    return Response({
        'cuestionario': {
            'id':     cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id':     periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados':            _build_filtros_aplicados(division_id, tutor_id, grupo_id, periodo_id, cuestionario_id),
        'total_grupos':                 len(grupos_ids),
        'total_alumnos':                total,
        'total_completados':            completados,
        'porcentaje_completado_global': porcentaje,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def alertas_comite_view(request):
    """
    Alertas de alumnos aislados (INVISIBLE) por división y por grupo.
    GET /api/comite/overview/alertas/

    Query params (todos opcionales):
    - periodo_id, cuestionario_id, division_id, tutor_id, grupo_id

    Response:
    {
        "cuestionario": { "id", "titulo", "activo" },
        "periodo": { "id", "codigo", "nombre" },
        "filtros_aplicados": {},
        "alertas_aislados": {
            "total_global": 12,
            "por_division": [ { "division_id", "division", "total_aislados" } ],
            "por_grupo": [ { "grupo_id", "grupo_clave", "division", "total_aislados" } ]
        }
    }
    """
    periodo_id      = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id     = request.query_params.get('division_id')
    tutor_id        = request.query_params.get('tutor_id')
    grupo_id        = request.query_params.get('grupo_id')

    cuestionario, periodo, error = _resolver_cuestionario(periodo_id, cuestionario_id)
    if error:
        return error

    grupos_qs = Grupo.objects.filter(
        periodo=periodo,
        activo=True
    ).select_related('programa', 'programa__division')
    grupos_qs = _aplicar_filtros_grupos(grupos_qs, division_id, tutor_id, grupo_id)

    if not grupos_qs.exists():
        return Response(
            {'error': 'No se encontraron grupos con los filtros especificados'},
            status=status.HTTP_404_NOT_FOUND
        )

    grupos_list = list(grupos_qs)

    # Batch: ~6 queries para todos los grupos
    nodos_por_grupo = _calcular_nodos_batch(cuestionario, grupos_list)

    alertas_por_grupo    = []
    alertas_por_division = {}
    total_aislados_global = 0

    for grupo in grupos_list:
        nodos = nodos_por_grupo.get(grupo.id, {}).get('nodos', [])
        aislados = [n for n in nodos if n['tipo'] == 'INVISIBLE']

        if not aislados:
            continue

        division_nombre = grupo.programa.division.nombre if grupo.programa and grupo.programa.division else 'Sin división'
        division_id_val = grupo.programa.division.id    if grupo.programa and grupo.programa.division else None

        alertas_por_grupo.append({
            'grupo_id':       grupo.id,
            'grupo_clave':    grupo.clave,
            'division':       division_nombre,
            'total_aislados': len(aislados),
        })
        total_aislados_global += len(aislados)

        key = division_id_val
        if key not in alertas_por_division:
            alertas_por_division[key] = {
                'division_id':    division_id_val,
                'division':       division_nombre,
                'total_aislados': 0
            }
        alertas_por_division[key]['total_aislados'] += len(aislados)

    return Response({
        'cuestionario': {
            'id':     cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id':     periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados': _build_filtros_aplicados(division_id, tutor_id, grupo_id, periodo_id, cuestionario_id),
        'alertas_aislados': {
            'total_global':  total_aislados_global,
            'por_division':  list(alertas_por_division.values()),
            'por_grupo':     alertas_por_grupo,
        },
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def centralidad_comite_view(request):
    """
    Top 10 de centralidad (puntos positivos recibidos) por división y por grupo.
    GET /api/comite/overview/centralidad/

    Query params (todos opcionales):
    - periodo_id, cuestionario_id, division_id, tutor_id, grupo_id

    Response:
    {
        "cuestionario": { "id", "titulo", "activo" },
        "periodo": { "id", "codigo", "nombre" },
        "filtros_aplicados": {},
        "top_centralidad": {
            "por_division": [ { "division_id", "division", "top": [...] } ],
            "por_grupo": [ { "grupo_id", "grupo_clave", "top": [...] } ]
        }
    }
    """
    periodo_id      = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id     = request.query_params.get('division_id')
    tutor_id        = request.query_params.get('tutor_id')
    grupo_id        = request.query_params.get('grupo_id')

    cuestionario, periodo, error = _resolver_cuestionario(periodo_id, cuestionario_id)
    if error:
        return error

    grupos_qs = Grupo.objects.filter(
        periodo=periodo,
        activo=True
    ).select_related('programa', 'programa__division', 'tutor', 'tutor__user')
    grupos_qs = _aplicar_filtros_grupos(grupos_qs, division_id, tutor_id, grupo_id)

    if not grupos_qs.exists():
        return Response(
            {'error': 'No se encontraron grupos con los filtros especificados'},
            status=status.HTTP_404_NOT_FOUND
        )

    grupos_list = list(grupos_qs)

    # Batch: ~6 queries para todos los grupos
    nodos_por_grupo = _calcular_nodos_batch(cuestionario, grupos_list)

    top_por_division   = {}
    top_por_grupo_dict = {}

    for grupo in grupos_list:
        gid   = grupo.id
        nodos = nodos_por_grupo.get(gid, {}).get('nodos', [])

        division_nombre = grupo.programa.division.nombre if grupo.programa and grupo.programa.division else 'Sin división'
        division_id_val = grupo.programa.division.id    if grupo.programa and grupo.programa.division else None

        if division_id_val not in top_por_division:
            top_por_division[division_id_val] = {
                'division_id': division_id_val,
                'division':    division_nombre,
                'alumnos':     []
            }
        if gid not in top_por_grupo_dict:
            top_por_grupo_dict[gid] = {
                'grupo_id':    gid,
                'grupo_clave': grupo.clave,
                'alumnos':     []
            }

        for nodo in nodos:
            entrada = {
                'alumno_id':           nodo['alumno_id'],
                'nombre':              nodo['nombre'],
                'matricula':           nodo['matricula'],
                'elecciones_positivas': nodo['puntos_positivos'],
                'grupo_clave':         grupo.clave,
            }
            top_por_division[division_id_val]['alumnos'].append(entrada)
            top_por_grupo_dict[gid]['alumnos'].append(entrada)

    # Top 10 por división
    top_centralidad_division = []
    for div_data in top_por_division.values():
        top_10 = sorted(div_data['alumnos'], key=lambda x: x['elecciones_positivas'], reverse=True)[:10]
        top_centralidad_division.append({
            'division_id': div_data['division_id'],
            'division':    div_data['division'],
            'top': [
                {
                    'alumno_id':           a['alumno_id'],
                    'nombre':              a['nombre'],
                    'matricula':           a['matricula'],
                    'elecciones_positivas': a['elecciones_positivas'],
                    'grupo':               a['grupo_clave'],
                }
                for a in top_10
            ]
        })

    # Top 10 por grupo
    top_centralidad_grupo = []
    for grp_data in top_por_grupo_dict.values():
        top_10 = sorted(grp_data['alumnos'], key=lambda x: x['elecciones_positivas'], reverse=True)[:10]
        top_centralidad_grupo.append({
            'grupo_id':    grp_data['grupo_id'],
            'grupo_clave': grp_data['grupo_clave'],
            'top': [
                {
                    'alumno_id':           a['alumno_id'],
                    'nombre':              a['nombre'],
                    'matricula':           a['matricula'],
                    'elecciones_positivas': a['elecciones_positivas'],
                }
                for a in top_10
            ]
        })

    return Response({
        'cuestionario': {
            'id':     cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id':     periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados': _build_filtros_aplicados(division_id, tutor_id, grupo_id, periodo_id, cuestionario_id),
        'top_centralidad': {
            'por_division': top_centralidad_division,
            'por_grupo':    top_centralidad_grupo,
        },
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def graphs_comite_view(request):
    """
    Distribución ACEPTADO/RECHAZADO/INVISIBLE por grupo para gráficas.
    GET /api/comite/graphs

    Query params (todos opcionales):
    - periodo_id, cuestionario_id, division_id, tutor_id, grupo_id

    Response:
    {
        "cuestionario": { "id", "titulo", "activo" },
        "periodo": { "id", "codigo", "nombre" },
        "filtros_aplicados": {},
        "distribucion_por_grupo": [
            {
                "grupo_id", "grupo_clave", "division", "programa",
                "ACEPTADO", "RECHAZADO", "INVISIBLE", "total"
            }
        ]
    }
    """
    periodo_id      = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id     = request.query_params.get('division_id')
    tutor_id        = request.query_params.get('tutor_id')
    grupo_id        = request.query_params.get('grupo_id')

    cuestionario, periodo, error = _resolver_cuestionario(periodo_id, cuestionario_id)
    if error:
        return error

    grupos_qs = Grupo.objects.filter(
        periodo=periodo,
        activo=True
    ).select_related('programa', 'programa__division')
    grupos_qs = _aplicar_filtros_grupos(grupos_qs, division_id, tutor_id, grupo_id)

    if not grupos_qs.exists():
        return Response(
            {'error': 'No se encontraron grupos con los filtros especificados'},
            status=status.HTTP_404_NOT_FOUND
        )

    grupos_list = list(grupos_qs)

    # Batch: ~6 queries para todos los grupos
    nodos_por_grupo = _calcular_nodos_batch(cuestionario, grupos_list)

    distribucion = []
    for grupo in grupos_list:
        nodos = nodos_por_grupo.get(grupo.id, {}).get('nodos', [])

        aceptados = sum(1 for n in nodos if n['tipo'] == 'ACEPTADO')
        rechazados = sum(1 for n in nodos if n['tipo'] == 'RECHAZADO')
        invisibles = sum(1 for n in nodos if n['tipo'] == 'INVISIBLE')

        distribucion.append({
            'grupo_id':    grupo.id,
            'grupo_clave': grupo.clave,
            'division':    grupo.programa.division.nombre if grupo.programa and grupo.programa.division else None,
            'programa':    grupo.programa.nombre if grupo.programa else None,
            'ACEPTADO':    aceptados,
            'RECHAZADO':   rechazados,
            'INVISIBLE':   invisibles,
            'total':       len(nodos),
        })

    return Response({
        'cuestionario': {
            'id':     cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id':     periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados':    _build_filtros_aplicados(division_id, tutor_id, grupo_id, periodo_id, cuestionario_id),
        'distribucion_por_grupo': distribucion,
    }, status=status.HTTP_200_OK)