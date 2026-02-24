# core/views/comite/dashboard.py
"""
Endpoints para Comité - Dashboard Global (Solo Lectura)

GET /api/comite/overview  — resumen ejecutivo global
GET /api/comite/graphs    — datos para graficas
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Case, When, IntegerField, Q

from core.models import (
    Cuestionario, CuestionarioEstado, Grupo, Respuesta,
    Periodo, AlumnoGrupo
)
from core.utils.decorators import require_comite_readonly
from core.views.academic.cuestionarios import (
    _calcular_nodos_sociograma,
    _clasificar_alumno,
)


def _resolver_cuestionario(periodo_id=None, cuestionario_id=None):
    """
    Resuelve qué cuestionario usar según los parámetros:
    - cuestionario_id → ese cuestionario específico (activo o no)
    - periodo_id      → cuestionario activo de ese periodo
    - ninguno         → cuestionario activo del periodo activo

    Retorna: (cuestionario, periodo, error_response)
    Si hay error retorna (None, None, Response)
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
        # Default: periodo activo
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
    """Aplica filtros opcionales a un queryset de grupos"""
    if division_id:
        grupos_qs = grupos_qs.filter(programa__division_id=division_id)
    if tutor_id:
        grupos_qs = grupos_qs.filter(tutor_id=tutor_id)
    if grupo_id:
        grupos_qs = grupos_qs.filter(id=grupo_id)
    return grupos_qs


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def overview_comite_view(request):
    """
    Resumen ejecutivo global para el Comité.

    GET /api/comite/overview

    Query params (todos opcionales):
    - periodo_id      : ver periodo histórico específico
    - cuestionario_id : ver cuestionario específico (activo o no)
    - division_id     : filtrar por división
    - tutor_id        : filtrar por tutor
    - grupo_id        : filtrar por grupo específico

    Default: periodo activo + cuestionario activo de ese periodo

    Response:
    {
        "cuestionario": { "id": 1, "titulo": "...", "activo": true },
        "periodo": { "id": 1, "codigo": "2026-1", "nombre": "..." },
        "filtros_aplicados": {},
        "total_grupos": 45,
        "porcentaje_completado_global": 72.5,
        "alertas_aislados": {
            "total_global": 12,
            "por_division": [ { "division_id": 1, "division": "TI", "total_aislados": 7 } ],
            "por_grupo": [ { "grupo_id": 1, "grupo_clave": "IDGS-5-A", "division": "TI", "total_aislados": 3 } ]
        },
        "top_centralidad": {
            "por_division": [
                {
                    "division_id": 1,
                    "division": "TI",
                    "top": [ { "alumno_id": 1, "nombre": "...", "matricula": "...", "elecciones_positivas": 24, "grupo": "IDGS-5-A" } ]
                }
            ],
            "por_grupo": [
                {
                    "grupo_id": 1,
                    "grupo_clave": "IDGS-5-A",
                    "top": [ { "alumno_id": 1, "nombre": "...", "matricula": "...", "elecciones_positivas": 18 } ]
                }
            ]
        }
    }
    """
    # Resolver parámetros
    periodo_id = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id = request.query_params.get('division_id')
    tutor_id = request.query_params.get('tutor_id')
    grupo_id = request.query_params.get('grupo_id')

    # Resolver cuestionario
    cuestionario, periodo, error = _resolver_cuestionario(periodo_id, cuestionario_id)
    if error:
        return error

    # Obtener grupos con filtros
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

    grupos_ids = list(grupos_qs.values_list('id', flat=True))

    # ============================================
    # PORCENTAJE COMPLETADO GLOBAL — una sola query
    # ============================================
    estados_agg = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        grupo_id__in=grupos_ids
    ).aggregate(
        total=Count('id'),
        completados=Count(Case(When(estado='COMPLETADO', then=1), output_field=IntegerField()))
    )

    total_estados = estados_agg['total'] or 0
    total_completados = estados_agg['completados'] or 0
    porcentaje_global = round(total_completados / total_estados * 100, 2) if total_estados > 0 else 0

    # ============================================
    # ALERTAS DE AISLADOS — calcular nodos por grupo
    # ============================================
    alertas_por_grupo = []
    alertas_por_division = {}
    total_aislados_global = 0

    for grupo in grupos_qs:
        nodos_data = _calcular_nodos_sociograma(cuestionario, grupo)
        aislados = [n for n in nodos_data['nodos'] if n['tipo'] == 'INVISIBLE']
        total_aislados = len(aislados)

        if total_aislados > 0:
            division_nombre = grupo.programa.division.nombre if grupo.programa and grupo.programa.division else 'Sin división'
            division_id_grupo = grupo.programa.division.id if grupo.programa and grupo.programa.division else None

            alertas_por_grupo.append({
                'grupo_id': grupo.id,
                'grupo_clave': grupo.clave,
                'division': division_nombre,
                'total_aislados': total_aislados,
            })

            total_aislados_global += total_aislados

            # Acumular por division
            key = division_id_grupo
            if key not in alertas_por_division:
                alertas_por_division[key] = {
                    'division_id': division_id_grupo,
                    'division': division_nombre,
                    'total_aislados': 0
                }
            alertas_por_division[key]['total_aislados'] += total_aislados

    # ============================================
    # TOP CENTRALIDAD (positivas) — una query batch
    # ============================================
    preguntas_positivas_ids = list(
        cuestionario.preguntas.filter(
            pregunta__tipo='SELECCION_ALUMNO',
            pregunta__polaridad='POSITIVA'
        ).values_list('pregunta_id', flat=True)
    )

    alumnos_ids = list(
        AlumnoGrupo.objects.filter(
            grupo_id__in=grupos_ids,
            activo=True
        ).values_list('alumno_id', flat=True)
    )

    # Elecciones positivas recibidas por alumno — una sola query
    elecciones_qs = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id__in=preguntas_positivas_ids,
        seleccionado_alumno_id__in=alumnos_ids
    ).values('seleccionado_alumno_id').annotate(
        elecciones_positivas=Count('id')
    )

    elecciones_map = {
        e['seleccionado_alumno_id']: e['elecciones_positivas']
        for e in elecciones_qs
    }

    # Mapear alumno → grupo y datos básicos
    alumno_grupo_map = {}
    for grupo in grupos_qs:
        ags = AlumnoGrupo.objects.filter(
            grupo=grupo,
            activo=True
        ).select_related('alumno', 'alumno__user')

        division_nombre = grupo.programa.division.nombre if grupo.programa and grupo.programa.division else 'Sin división'
        division_id_val = grupo.programa.division.id if grupo.programa and grupo.programa.division else None

        for ag in ags:
            alumno = ag.alumno
            alumno_grupo_map[alumno.id] = {
                'alumno_id': alumno.id,
                'nombre': alumno.user.nombre_completo,
                'matricula': alumno.matricula,
                'elecciones_positivas': elecciones_map.get(alumno.id, 0),
                'grupo_id': grupo.id,
                'grupo_clave': grupo.clave,
                'division_id': division_id_val,
                'division': division_nombre,
            }

    # Top 10 por división
    top_por_division = {}
    for alumno_data in alumno_grupo_map.values():
        div_id = alumno_data['division_id']
        if div_id not in top_por_division:
            top_por_division[div_id] = {
                'division_id': div_id,
                'division': alumno_data['division'],
                'alumnos': []
            }
        top_por_division[div_id]['alumnos'].append(alumno_data)

    top_centralidad_division = []
    for div_data in top_por_division.values():
        top_10 = sorted(
            div_data['alumnos'],
            key=lambda x: x['elecciones_positivas'],
            reverse=True
        )[:10]
        top_centralidad_division.append({
            'division_id': div_data['division_id'],
            'division': div_data['division'],
            'top': [
                {
                    'alumno_id': a['alumno_id'],
                    'nombre': a['nombre'],
                    'matricula': a['matricula'],
                    'elecciones_positivas': a['elecciones_positivas'],
                    'grupo': a['grupo_clave'],
                }
                for a in top_10
            ]
        })

    # Top 10 por grupo
    top_por_grupo_dict = {}
    for alumno_data in alumno_grupo_map.values():
        g_id = alumno_data['grupo_id']
        if g_id not in top_por_grupo_dict:
            top_por_grupo_dict[g_id] = {
                'grupo_id': g_id,
                'grupo_clave': alumno_data['grupo_clave'],
                'alumnos': []
            }
        top_por_grupo_dict[g_id]['alumnos'].append(alumno_data)

    top_centralidad_grupo = []
    for grp_data in top_por_grupo_dict.values():
        top_10 = sorted(
            grp_data['alumnos'],
            key=lambda x: x['elecciones_positivas'],
            reverse=True
        )[:10]
        top_centralidad_grupo.append({
            'grupo_id': grp_data['grupo_id'],
            'grupo_clave': grp_data['grupo_clave'],
            'top': [
                {
                    'alumno_id': a['alumno_id'],
                    'nombre': a['nombre'],
                    'matricula': a['matricula'],
                    'elecciones_positivas': a['elecciones_positivas'],
                }
                for a in top_10
            ]
        })

    # Filtros aplicados
    filtros_aplicados = {}
    if division_id:
        filtros_aplicados['division_id'] = division_id
    if tutor_id:
        filtros_aplicados['tutor_id'] = tutor_id
    if grupo_id:
        filtros_aplicados['grupo_id'] = grupo_id
    if periodo_id:
        filtros_aplicados['periodo_id'] = periodo_id
    if cuestionario_id:
        filtros_aplicados['cuestionario_id'] = cuestionario_id

    return Response({
        'cuestionario': {
            'id': cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados': filtros_aplicados,
        'total_grupos': len(grupos_ids),
        'porcentaje_completado_global': porcentaje_global,
        'alertas_aislados': {
            'total_global': total_aislados_global,
            'por_division': list(alertas_por_division.values()),
            'por_grupo': alertas_por_grupo,
        },
        'top_centralidad': {
            'por_division': top_centralidad_division,
            'por_grupo': top_centralidad_grupo,
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
        "cuestionario": { "id": 1, "titulo": "...", "activo": true },
        "periodo": { "id": 1, "codigo": "2026-1" },
        "filtros_aplicados": {},
        "total_grupos": 45,
        "total_alumnos": 1200,
        "total_completados": 870,
        "porcentaje_completado_global": 72.5
    }
    """
    periodo_id = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id = request.query_params.get('division_id')
    tutor_id = request.query_params.get('tutor_id')
    grupo_id = request.query_params.get('grupo_id')

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

    estados_agg = CuestionarioEstado.objects.filter(
        cuestionario=cuestionario,
        grupo_id__in=grupos_ids
    ).aggregate(
        total=Count('id'),
        completados=Count(Case(When(estado='COMPLETADO', then=1), output_field=IntegerField()))
    )

    total = estados_agg['total'] or 0
    completados = estados_agg['completados'] or 0
    porcentaje = round(completados / total * 100, 2) if total > 0 else 0

    filtros_aplicados = {}
    if division_id:
        filtros_aplicados['division_id'] = division_id
    if tutor_id:
        filtros_aplicados['tutor_id'] = tutor_id
    if grupo_id:
        filtros_aplicados['grupo_id'] = grupo_id
    if periodo_id:
        filtros_aplicados['periodo_id'] = periodo_id
    if cuestionario_id:
        filtros_aplicados['cuestionario_id'] = cuestionario_id

    return Response({
        'cuestionario': {
            'id': cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados': filtros_aplicados,
        'total_grupos': len(grupos_ids),
        'total_alumnos': total,
        'total_completados': completados,
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
        "cuestionario": { "id": 1, "titulo": "...", "activo": true },
        "periodo": { "id": 1, "codigo": "2026-1" },
        "filtros_aplicados": {},
        "alertas_aislados": {
            "total_global": 12,
            "por_division": [
                { "division_id": 1, "division": "TI", "total_aislados": 7 }
            ],
            "por_grupo": [
                { "grupo_id": 1, "grupo_clave": "IDGS-5-A", "division": "TI", "total_aislados": 3 }
            ]
        }
    }
    """
    periodo_id = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id = request.query_params.get('division_id')
    tutor_id = request.query_params.get('tutor_id')
    grupo_id = request.query_params.get('grupo_id')

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

    alertas_por_grupo = []
    alertas_por_division = {}
    total_aislados_global = 0

    for grupo in grupos_qs:
        nodos_data = _calcular_nodos_sociograma(cuestionario, grupo)
        aislados = [n for n in nodos_data['nodos'] if n['tipo'] == 'INVISIBLE']
        total_aislados = len(aislados)

        if total_aislados > 0:
            division_nombre = grupo.programa.division.nombre if grupo.programa and grupo.programa.division else 'Sin división'
            division_id_grupo = grupo.programa.division.id if grupo.programa and grupo.programa.division else None

            alertas_por_grupo.append({
                'grupo_id': grupo.id,
                'grupo_clave': grupo.clave,
                'division': division_nombre,
                'total_aislados': total_aislados,
            })

            total_aislados_global += total_aislados

            key = division_id_grupo
            if key not in alertas_por_division:
                alertas_por_division[key] = {
                    'division_id': division_id_grupo,
                    'division': division_nombre,
                    'total_aislados': 0
                }
            alertas_por_division[key]['total_aislados'] += total_aislados

    filtros_aplicados = {}
    if division_id:
        filtros_aplicados['division_id'] = division_id
    if tutor_id:
        filtros_aplicados['tutor_id'] = tutor_id
    if grupo_id:
        filtros_aplicados['grupo_id'] = grupo_id
    if periodo_id:
        filtros_aplicados['periodo_id'] = periodo_id
    if cuestionario_id:
        filtros_aplicados['cuestionario_id'] = cuestionario_id

    return Response({
        'cuestionario': {
            'id': cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados': filtros_aplicados,
        'alertas_aislados': {
            'total_global': total_aislados_global,
            'por_division': list(alertas_por_division.values()),
            'por_grupo': alertas_por_grupo,
        },
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def centralidad_comite_view(request):
    """
    Top 10 de centralidad (elecciones positivas recibidas) por división y por grupo.

    GET /api/comite/overview/centralidad/

    Query params (todos opcionales):
    - periodo_id, cuestionario_id, division_id, tutor_id, grupo_id

    Response:
    {
        "cuestionario": { "id": 1, "titulo": "...", "activo": true },
        "periodo": { "id": 1, "codigo": "2026-1" },
        "filtros_aplicados": {},
        "top_centralidad": {
            "por_division": [
                {
                    "division_id": 1,
                    "division": "TI",
                    "top": [
                        { "alumno_id": 1, "nombre": "...", "matricula": "...", "elecciones_positivas": 24, "grupo": "IDGS-5-A" }
                    ]
                }
            ],
            "por_grupo": [
                {
                    "grupo_id": 1,
                    "grupo_clave": "IDGS-5-A",
                    "top": [
                        { "alumno_id": 1, "nombre": "...", "matricula": "...", "elecciones_positivas": 18 }
                    ]
                }
            ]
        }
    }
    """
    periodo_id = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id = request.query_params.get('division_id')
    tutor_id = request.query_params.get('tutor_id')
    grupo_id = request.query_params.get('grupo_id')

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

    grupos_ids = list(grupos_qs.values_list('id', flat=True))

    # Preguntas positivas
    preguntas_positivas_ids = list(
        cuestionario.preguntas.filter(
            pregunta__tipo='SELECCION_ALUMNO',
            pregunta__polaridad='POSITIVA'
        ).values_list('pregunta_id', flat=True)
    )

    alumnos_ids = list(
        AlumnoGrupo.objects.filter(
            grupo_id__in=grupos_ids,
            activo=True
        ).values_list('alumno_id', flat=True)
    )

    # Elecciones positivas por alumno — una sola query
    elecciones_qs = Respuesta.objects.filter(
        cuestionario=cuestionario,
        pregunta_id__in=preguntas_positivas_ids,
        seleccionado_alumno_id__in=alumnos_ids
    ).values('seleccionado_alumno_id').annotate(
        elecciones_positivas=Count('id')
    )

    elecciones_map = {
        e['seleccionado_alumno_id']: e['elecciones_positivas']
        for e in elecciones_qs
    }

    # Mapear alumno → grupo y división
    alumno_grupo_map = {}
    for grupo in grupos_qs:
        ags = AlumnoGrupo.objects.filter(
            grupo=grupo,
            activo=True
        ).select_related('alumno', 'alumno__user')

        division_nombre = grupo.programa.division.nombre if grupo.programa and grupo.programa.division else 'Sin división'
        division_id_val = grupo.programa.division.id if grupo.programa and grupo.programa.division else None

        for ag in ags:
            alumno = ag.alumno
            alumno_grupo_map[alumno.id] = {
                'alumno_id': alumno.id,
                'nombre': alumno.user.nombre_completo,
                'matricula': alumno.matricula,
                'elecciones_positivas': elecciones_map.get(alumno.id, 0),
                'grupo_id': grupo.id,
                'grupo_clave': grupo.clave,
                'division_id': division_id_val,
                'division': division_nombre,
            }

    # Top 10 por división
    top_por_division = {}
    for alumno_data in alumno_grupo_map.values():
        div_id = alumno_data['division_id']
        if div_id not in top_por_division:
            top_por_division[div_id] = {
                'division_id': div_id,
                'division': alumno_data['division'],
                'alumnos': []
            }
        top_por_division[div_id]['alumnos'].append(alumno_data)

    top_centralidad_division = []
    for div_data in top_por_division.values():
        top_10 = sorted(
            div_data['alumnos'],
            key=lambda x: x['elecciones_positivas'],
            reverse=True
        )[:10]
        top_centralidad_division.append({
            'division_id': div_data['division_id'],
            'division': div_data['division'],
            'top': [
                {
                    'alumno_id': a['alumno_id'],
                    'nombre': a['nombre'],
                    'matricula': a['matricula'],
                    'elecciones_positivas': a['elecciones_positivas'],
                    'grupo': a['grupo_clave'],
                }
                for a in top_10
            ]
        })

    # Top 10 por grupo
    top_por_grupo_dict = {}
    for alumno_data in alumno_grupo_map.values():
        g_id = alumno_data['grupo_id']
        if g_id not in top_por_grupo_dict:
            top_por_grupo_dict[g_id] = {
                'grupo_id': g_id,
                'grupo_clave': alumno_data['grupo_clave'],
                'alumnos': []
            }
        top_por_grupo_dict[g_id]['alumnos'].append(alumno_data)

    top_centralidad_grupo = []
    for grp_data in top_por_grupo_dict.values():
        top_10 = sorted(
            grp_data['alumnos'],
            key=lambda x: x['elecciones_positivas'],
            reverse=True
        )[:10]
        top_centralidad_grupo.append({
            'grupo_id': grp_data['grupo_id'],
            'grupo_clave': grp_data['grupo_clave'],
            'top': [
                {
                    'alumno_id': a['alumno_id'],
                    'nombre': a['nombre'],
                    'matricula': a['matricula'],
                    'elecciones_positivas': a['elecciones_positivas'],
                }
                for a in top_10
            ]
        })

    filtros_aplicados = {}
    if division_id:
        filtros_aplicados['division_id'] = division_id
    if tutor_id:
        filtros_aplicados['tutor_id'] = tutor_id
    if grupo_id:
        filtros_aplicados['grupo_id'] = grupo_id
    if periodo_id:
        filtros_aplicados['periodo_id'] = periodo_id
    if cuestionario_id:
        filtros_aplicados['cuestionario_id'] = cuestionario_id

    return Response({
        'cuestionario': {
            'id': cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados': filtros_aplicados,
        'top_centralidad': {
            'por_division': top_centralidad_division,
            'por_grupo': top_centralidad_grupo,
        },
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_comite_readonly
def graphs_comite_view(request):
    """
    Datos para gráficas del dashboard del Comité.
    Distribución ACEPTADO/RECHAZADO/INVISIBLE por grupo.

    GET /api/comite/graphs

    Query params (todos opcionales):
    - periodo_id      : ver periodo histórico específico
    - cuestionario_id : ver cuestionario específico (activo o no)
    - division_id     : filtrar por división
    - tutor_id        : filtrar por tutor
    - grupo_id        : filtrar por grupo específico

    Response:
    {
        "cuestionario": { "id": 1, "titulo": "..." },
        "periodo": { "id": 1, "codigo": "2026-1" },
        "filtros_aplicados": {},
        "distribucion_por_grupo": [
            {
                "grupo_id": 1,
                "grupo_clave": "IDGS-5-A",
                "division": "TI",
                "programa": "Ing. Desarrollo de Software",
                "ACEPTADO": 18,
                "RECHAZADO": 4,
                "INVISIBLE": 3,
                "total": 25
            }
        ]
    }
    """
    periodo_id = request.query_params.get('periodo_id')
    cuestionario_id = request.query_params.get('cuestionario_id')
    division_id = request.query_params.get('division_id')
    tutor_id = request.query_params.get('tutor_id')
    grupo_id = request.query_params.get('grupo_id')

    # Resolver cuestionario
    cuestionario, periodo, error = _resolver_cuestionario(periodo_id, cuestionario_id)
    if error:
        return error

    # Obtener grupos con filtros
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

    # Calcular distribución por grupo
    distribucion = []

    for grupo in grupos_qs:
        nodos_data = _calcular_nodos_sociograma(cuestionario, grupo)
        nodos = nodos_data['nodos']

        aceptados = sum(1 for n in nodos if n['tipo'] == 'ACEPTADO')
        rechazados = sum(1 for n in nodos if n['tipo'] == 'RECHAZADO')
        invisibles = sum(1 for n in nodos if n['tipo'] == 'INVISIBLE')

        distribucion.append({
            'grupo_id': grupo.id,
            'grupo_clave': grupo.clave,
            'division': grupo.programa.division.nombre if grupo.programa and grupo.programa.division else None,
            'programa': grupo.programa.nombre if grupo.programa else None,
            'ACEPTADO': aceptados,
            'RECHAZADO': rechazados,
            'INVISIBLE': invisibles,
            'total': len(nodos),
        })

    filtros_aplicados = {}
    if division_id:
        filtros_aplicados['division_id'] = division_id
    if tutor_id:
        filtros_aplicados['tutor_id'] = tutor_id
    if grupo_id:
        filtros_aplicados['grupo_id'] = grupo_id
    if periodo_id:
        filtros_aplicados['periodo_id'] = periodo_id
    if cuestionario_id:
        filtros_aplicados['cuestionario_id'] = cuestionario_id

    return Response({
        'cuestionario': {
            'id': cuestionario.id,
            'titulo': cuestionario.titulo,
            'activo': cuestionario.activo,
        },
        'periodo': {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
        },
        'filtros_aplicados': filtros_aplicados,
        'distribucion_por_grupo': distribucion,
    }, status=status.HTTP_200_OK)