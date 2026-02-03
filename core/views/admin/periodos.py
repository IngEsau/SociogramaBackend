# core/views/periodos.py (NUEVO ARCHIVO)
"""
Endpoints para gestión de periodos
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

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
    periodos = Periodo.objects.all().order_by('-codigo')
    
    periodos_data = []
    for periodo in periodos:
        grupos_count = Grupo.objects.filter(periodo=periodo, activo=1).count()
        alumnos_count = AlumnoGrupo.objects.filter(
            grupo__periodo=periodo,
            activo=1
        ).count()
        
        periodos_data.append({
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': periodo.activo == 1,
            'fecha_inicio': periodo.fecha_inicio.isoformat() if periodo.fecha_inicio else None,
            'fecha_fin': periodo.fecha_fin.isoformat() if periodo.fecha_fin else None,
            'grupos_count': grupos_count,
            'alumnos_count': alumnos_count,
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
            "inscripciones_desactivadas": 10000
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
        'grupos_reactivados': 0,  # ← NUEVO
        'inscripciones_reactivadas': 0,  # ← NUEVO
    }
    
    with transaction.atomic():
        # 1. ACTIVAR EL PERIODO SELECCIONADO
        Periodo.objects.filter(id=periodo_id).update(activo=1)
        
        # 2. REACTIVAR GRUPOS E INSCRIPCIONES DEL PERIODO ← NUEVO
        cambios['grupos_reactivados'] = Grupo.objects.filter(
            periodo_id=periodo_id
        ).update(activo=1)
        
        cambios['inscripciones_reactivadas'] = AlumnoGrupo.objects.filter(
            grupo__periodo_id=periodo_id
        ).update(activo=1)
        
        # 3. DESACTIVAR LOS DEMÁS (si se pidió)
        if desactivar_otros:
            cambios['periodos_desactivados'] = Periodo.objects.exclude(
                id=periodo_id
            ).filter(activo=1).update(activo=0)
            
            cambios['grupos_desactivados'] = Grupo.objects.filter(
                periodo__activo=0,
                activo=1
            ).update(activo=0)
            
            cambios['inscripciones_desactivadas'] = AlumnoGrupo.objects.filter(
                grupo__periodo__activo=0,
                activo=1
            ).update(activo=0)
    
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
        # Desactivar el periodo
        Periodo.objects.filter(id=periodo_id).update(activo=0)
        
        # Desactivar sus grupos
        cambios['grupos_desactivados'] = Grupo.objects.filter(
            periodo_id=periodo_id,
            activo=1
        ).update(activo=0)
        
        # Desactivar sus inscripciones
        cambios['inscripciones_desactivadas'] = AlumnoGrupo.objects.filter(
            grupo__periodo_id=periodo_id,
            activo=1
        ).update(activo=0)
    
    # Refrescar el objeto periodo
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
    
    # Validar datos
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
    
    # Generar datos del periodo
    codigo = generar_codigo_periodo(anio, numero)
    nombre = generar_nombre_periodo(anio, numero)
    fecha_inicio, fecha_fin = generar_fechas_periodo(anio, numero)
    
    # Verificar si ya existe
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
    
    # Crear periodo
    with transaction.atomic():
        periodo = Periodo.objects.create(
            codigo=codigo,
            nombre=nombre,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            activo=1 if activar_inmediatamente else 0
        )
        
        # Si se debe activar inmediatamente, desactivar los demás
        if activar_inmediatamente:
            Periodo.objects.exclude(id=periodo.id).update(activo=0)
            Grupo.objects.filter(periodo__activo=0, activo=1).update(activo=0)
            AlumnoGrupo.objects.filter(grupo__periodo__activo=0, activo=1).update(activo=0)
    
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
        # Si hay múltiples activos, tomar el más reciente
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