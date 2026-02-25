# core/views/admin/periodos.py
"""
Endpoints para gestión de periodos
OPTIMIZADO: SQL directo para operaciones masivas, annotations para N+1
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, connection

from core.models import Periodo, Grupo, AlumnoGrupo
from core.utils.decorators import require_admin


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_admin
def listar_periodos_view(request):
    """
    Lista todos los periodos con su información

    GET /api/admin/periodos/

    Response:
    {
        "periodos": [
            {
                "id": 1,
                "codigo": "2026-1",
                "nombre": "Enero - Abril 2026",
                "activo": true,
                "fecha_inicio": "2026-01-15",
                "fecha_fin": "2026-04-30",
                "grupos_count": 235,
                "alumnos_count": 5904
            }
        ]
    }
    """
    # 1 sola query con annotations en lugar de N+1 queries en loop
    from django.db.models import Count, Q

    periodos = Periodo.objects.annotate(
        grupos_count=Count(
            'grupos__id',
            filter=Q(grupos__activo=True),
            distinct=True
        ),
        alumnos_count=Count(
            'grupos__alumnos__id',
            filter=Q(grupos__alumnos__activo=True),
            distinct=True
        )
    ).order_by('-codigo')

    periodos_data = []
    for periodo in periodos:
        periodos_data.append({
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': periodo.activo == 1,
            'fecha_inicio': periodo.fecha_inicio.isoformat() if periodo.fecha_inicio else None,
            'fecha_fin': periodo.fecha_fin.isoformat() if periodo.fecha_fin else None,
            'grupos_count': periodo.grupos_count,
            'alumnos_count': periodo.alumnos_count,
        })

    return Response({
        'periodos': periodos_data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def activar_periodo_view(request, periodo_id):
    """
    Activa un periodo y desactiva todos los demás

    POST /api/admin/periodos/{periodo_id}/activar/

    Body (opcional):
    {
        "desactivar_otros": true  // Default: true
    }

    Response:
    {
        "success": true,
        "periodo": {
            "id": 1,
            "codigo": "2026-1",
            "nombre": "Enero - Abril 2026",
            "activo": true
        },
        "cambios": {
            "periodos_desactivados": 3,
            "grupos_desactivados": 500,
            "inscripciones_desactivadas": 10000,
            "grupos_reactivados": 235,
            "inscripciones_reactivadas": 5904
        }
    }
    """
    try:
        periodo = Periodo.objects.get(id=periodo_id)
    except Periodo.DoesNotExist:
        return Response(
            {'error': 'Periodo no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )

    desactivar_otros = request.data.get('desactivar_otros', True)

    cambios = {
        'periodos_desactivados': 0,
        'grupos_desactivados': 0,
        'inscripciones_desactivadas': 0,
        'grupos_reactivados': 0,
        'inscripciones_reactivadas': 0,
    }

    with transaction.atomic():
        with connection.cursor() as cursor:

            # 1. ACTIVAR EL PERIODO SELECCIONADO
            cursor.execute(
                "UPDATE periodos SET activo = 1 WHERE id = %s",
                [periodo_id]
            )

            # 2. REACTIVAR GRUPOS DEL PERIODO SELECCIONADO
            # SQL directo evita subquery anidada de Django ORM
            cursor.execute(
                "UPDATE grupos SET activo = 1 WHERE periodo_id = %s",
                [periodo_id]
            )
            cambios['grupos_reactivados'] = cursor.rowcount

            # 3. REACTIVAR INSCRIPCIONES DEL PERIODO SELECCIONADO
            # JOIN directo: mucho más eficiente que la subquery anidada del ORM
            cursor.execute("""
                UPDATE alumno_grupo ag
                INNER JOIN grupos g ON ag.grupo_id = g.id
                SET ag.activo = 1
                WHERE g.periodo_id = %s
            """, [periodo_id])
            cambios['inscripciones_reactivadas'] = cursor.rowcount

            if desactivar_otros:
                # 4. DESACTIVAR PERIODOS (excluyendo el activado)
                cursor.execute(
                    "UPDATE periodos SET activo = 0 WHERE id != %s AND activo = 1",
                    [periodo_id]
                )
                cambios['periodos_desactivados'] = cursor.rowcount

                # 5. DESACTIVAR GRUPOS DE PERIODOS INACTIVOS
                # JOIN directo en lugar de subquery anidada
                cursor.execute("""
                    UPDATE grupos g
                    INNER JOIN periodos p ON g.periodo_id = p.id
                    SET g.activo = 0
                    WHERE p.activo = 0
                      AND g.activo = 1
                """)
                cambios['grupos_desactivados'] = cursor.rowcount

                # 6. DESACTIVAR INSCRIPCIONES DE GRUPOS INACTIVOS
                # JOIN de 3 tablas directo — el más costoso, ahora eficiente
                cursor.execute("""
                    UPDATE alumno_grupo ag
                    INNER JOIN grupos g ON ag.grupo_id = g.id
                    INNER JOIN periodos p ON g.periodo_id = p.id
                    SET ag.activo = 0
                    WHERE p.activo = 0
                      AND ag.activo = 1
                """)
                cambios['inscripciones_desactivadas'] = cursor.rowcount

    periodo.refresh_from_db()

    return Response({
        'success': True,
        'periodo': {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': periodo.activo == 1,
        },
        'cambios': cambios
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def desactivar_periodo_view(request, periodo_id):
    """
    Desactiva un periodo específico

    POST /api/admin/periodos/{periodo_id}/desactivar/

    Response:
    {
        "success": true,
        "periodo": {
            "id": 1,
            "codigo": "2026-1",
            "nombre": "Enero - Abril 2026",
            "activo": false
        },
        "cambios": {
            "grupos_desactivados": 235,
            "inscripciones_desactivadas": 5904
        }
    }
    """
    try:
        periodo = Periodo.objects.get(id=periodo_id)
    except Periodo.DoesNotExist:
        return Response(
            {'error': 'Periodo no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )

    cambios = {
        'grupos_desactivados': 0,
        'inscripciones_desactivadas': 0,
    }

    with transaction.atomic():
        with connection.cursor() as cursor:

            # 1. DESACTIVAR EL PERIODO
            cursor.execute(
                "UPDATE periodos SET activo = 0 WHERE id = %s",
                [periodo_id]
            )

            # 2. DESACTIVAR GRUPOS DEL PERIODO
            cursor.execute(
                "UPDATE grupos SET activo = 0 WHERE periodo_id = %s AND activo = 1",
                [periodo_id]
            )
            cambios['grupos_desactivados'] = cursor.rowcount

            # 3. DESACTIVAR INSCRIPCIONES DEL PERIODO
            # JOIN directo en lugar de subquery anidada del ORM
            cursor.execute("""
                UPDATE alumno_grupo ag
                INNER JOIN grupos g ON ag.grupo_id = g.id
                SET ag.activo = 0
                WHERE g.periodo_id = %s
                  AND ag.activo = 1
            """, [periodo_id])
            cambios['inscripciones_desactivadas'] = cursor.rowcount

    periodo.refresh_from_db()

    return Response({
        'success': True,
        'periodo': {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': periodo.activo == 1,
        },
        'cambios': cambios
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def crear_periodo_view(request):
    """
    Crea un nuevo periodo

    POST /api/admin/periodos/crear/

    Body:
    {
        "anio": 2026,
        "numero": 2,  // 1, 2 o 3
        "activar_inmediatamente": false  // Opcional, default: false
    }

    Response:
    {
        "success": true,
        "periodo": {
            "id": 5,
            "codigo": "2026-2",
            "nombre": "Mayo - Agosto 2026",
            "activo": false,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-08-31"
        },
        "created": true
    }
    """
    from core.utils.import_excel_helpers import (
        generar_codigo_periodo,
        generar_nombre_periodo,
        generar_fechas_periodo
    )

    anio = request.data.get('anio')
    numero = request.data.get('numero')
    activar_inmediatamente = request.data.get('activar_inmediatamente', False)

    if not anio or not numero:
        return Response(
            {'error': 'Se requieren los campos: anio y numero'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if numero not in [1, 2, 3]:
        return Response(
            {'error': 'El número de periodo debe ser 1, 2 o 3'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        anio = int(anio)
        numero = int(numero)
    except ValueError:
        return Response(
            {'error': 'Año y número deben ser enteros'},
            status=status.HTTP_400_BAD_REQUEST
        )

    codigo = generar_codigo_periodo(anio, numero)
    nombre = generar_nombre_periodo(anio, numero)
    fecha_inicio, fecha_fin = generar_fechas_periodo(anio, numero)

    if Periodo.objects.filter(codigo=codigo).exists():
        periodo_existente = Periodo.objects.get(codigo=codigo)
        return Response(
            {
                'success': False,
                'error': f'El periodo {codigo} ya existe',
                'periodo': {
                    'id': periodo_existente.id,
                    'codigo': periodo_existente.codigo,
                    'nombre': periodo_existente.nombre,
                    'activo': periodo_existente.activo == 1,
                },
                'created': False
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        with connection.cursor() as cursor:
            periodo = Periodo.objects.create(
                codigo=codigo,
                nombre=nombre,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                activo=1 if activar_inmediatamente else 0
            )

            if activar_inmediatamente:
                # Desactivar periodos
                cursor.execute(
                    "UPDATE periodos SET activo = 0 WHERE id != %s AND activo = 1",
                    [periodo.id]
                )
                # Desactivar grupos de periodos inactivos
                cursor.execute("""
                    UPDATE grupos g
                    INNER JOIN periodos p ON g.periodo_id = p.id
                    SET g.activo = 0
                    WHERE p.activo = 0 AND g.activo = 1
                """)
                # Desactivar inscripciones
                cursor.execute("""
                    UPDATE alumno_grupo ag
                    INNER JOIN grupos g ON ag.grupo_id = g.id
                    INNER JOIN periodos p ON g.periodo_id = p.id
                    SET ag.activo = 0
                    WHERE p.activo = 0 AND ag.activo = 1
                """)

    return Response({
        'success': True,
        'periodo': {
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': periodo.activo == 1,
            'fecha_inicio': periodo.fecha_inicio.isoformat(),
            'fecha_fin': periodo.fecha_fin.isoformat(),
        },
        'created': True
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obtener_periodo_activo_view(request):
    """
    Obtiene el periodo actualmente activo

    GET /api/periodos/activo/

    Response:
    {
        "periodo": {
            "id": 1,
            "codigo": "2026-1",
            "nombre": "Enero - Abril 2026",
            "activo": true,
            "fecha_inicio": "2026-01-15",
            "fecha_fin": "2026-04-30"
        }
    }
    """
    try:
        periodo = Periodo.objects.get(activo=1)

        return Response({
            'periodo': {
                'id': periodo.id,
                'codigo': periodo.codigo,
                'nombre': periodo.nombre,
                'activo': True,
                'fecha_inicio': periodo.fecha_inicio.isoformat() if periodo.fecha_inicio else None,
                'fecha_fin': periodo.fecha_fin.isoformat() if periodo.fecha_fin else None,
            }
        }, status=status.HTTP_200_OK)

    except Periodo.DoesNotExist:
        return Response(
            {'error': 'No hay ningún periodo activo'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Periodo.MultipleObjectsReturned:
        periodo = Periodo.objects.filter(activo=1).order_by('-codigo').first()

        return Response({
            'periodo': {
                'id': periodo.id,
                'codigo': periodo.codigo,
                'nombre': periodo.nombre,
                'activo': True,
                'fecha_inicio': periodo.fecha_inicio.isoformat() if periodo.fecha_inicio else None,
                'fecha_fin': periodo.fecha_fin.isoformat() if periodo.fecha_fin else None,
            },
            'warning': 'Hay múltiples periodos activos, se retornó el más reciente'
        }, status=status.HTTP_200_OK)