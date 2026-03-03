# core/views/admin/catalogos.py
"""
Endpoints CRUD de Catálogos
División y Programa: create / update / list
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import Division, Programa, Auditoria
from core.utils.decorators import require_admin


def _get_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# =============================================================================
# DIVISIONES
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_admin
def listar_divisiones_view(request):
    """
    Lista todas las divisiones.

    GET /api/admin/catalogos/divisiones/

    Response:
    {
        "divisiones": [
            { "id": 1, "codigo": "TI", "nombre": "Tecnologías de la Información", "activa": true }
        ]
    }
    """
    divisiones = Division.objects.all().order_by('nombre')
    data = [
        {
            'id': d.id,
            'codigo': d.codigo,
            'nombre': d.nombre,
            'descripcion': d.descripcion,
            'activa': d.activa,
        }
        for d in divisiones
    ]
    return Response({'divisiones': data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def crear_division_view(request):
    """
    Crea una nueva división.

    POST /api/admin/catalogos/divisiones/crear/
    Body:
    {
        "codigo": "TI",
        "nombre": "Tecnologías de la Información",
        "descripcion": ""   // opcional
    }

    Response:
    {
        "success": true,
        "division": { "id": 1, "codigo": "TI", "nombre": "...", "activa": true }
    }
    """
    codigo = request.data.get('codigo', '').strip().upper()
    nombre = request.data.get('nombre', '').strip()
    descripcion = request.data.get('descripcion', '').strip() or None

    if not codigo or not nombre:
        return Response(
            {'error': 'Se requieren los campos: codigo, nombre'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if Division.objects.filter(codigo=codigo).exists():
        return Response(
            {'error': f'Ya existe una división con el código {codigo}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    division = Division.objects.create(
        codigo=codigo,
        nombre=nombre,
        descripcion=descripcion,
        activa=True,
    )

    Auditoria.objects.create(
        usuario=request.user,
        accion='CREAR_DIVISION',
        entidad='division',
        entidad_id=division.id,
        detalle={'codigo': division.codigo, 'nombre': division.nombre},
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'division': {
            'id': division.id,
            'codigo': division.codigo,
            'nombre': division.nombre,
            'descripcion': division.descripcion,
            'activa': division.activa,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@require_admin
def editar_division_view(request, division_id):
    """
    Edita una división existente.

    PATCH /api/admin/catalogos/divisiones/<division_id>/editar/
    Body (todos opcionales):
    {
        "nombre": "Nuevo nombre",
        "descripcion": "...",
        "activa": false
    }

    Response:
    {
        "success": true,
        "division": { "id": 1, "codigo": "TI", "nombre": "...", "activa": true }
    }
    """
    try:
        division = Division.objects.get(id=division_id)
    except Division.DoesNotExist:
        return Response({'error': 'División no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    CAMPOS_EDITABLES = ['nombre', 'descripcion', 'activa']
    cambios = {}

    for campo in CAMPOS_EDITABLES:
        if campo in request.data:
            cambios[campo] = {'anterior': str(getattr(division, campo)), 'nuevo': str(request.data[campo])}
            setattr(division, campo, request.data[campo])

    if not cambios:
        return Response({'error': 'No se proporcionaron campos a editar'}, status=status.HTTP_400_BAD_REQUEST)

    division.save()

    Auditoria.objects.create(
        usuario=request.user,
        accion='EDITAR_DIVISION',
        entidad='division',
        entidad_id=division.id,
        detalle={'cambios': cambios},
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'division': {
            'id': division.id,
            'codigo': division.codigo,
            'nombre': division.nombre,
            'descripcion': division.descripcion,
            'activa': division.activa,
        }
    }, status=status.HTTP_200_OK)


# =============================================================================
# PROGRAMAS
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_admin
def listar_programas_view(request):
    """
    Lista todos los programas, con filtro opcional por división.

    GET /api/admin/catalogos/programas/
    Query params:
        - division_id: filtrar por división

    Response:
    {
        "programas": [
            {
                "id": 1,
                "codigo": "ISC",
                "nombre": "Ingeniería en Sistemas",
                "division_id": 1,
                "division_nombre": "TI",
                "duracion_semestres": 9,
                "activo": true
            }
        ]
    }
    """
    qs = Programa.objects.select_related('division').order_by('nombre')

    division_id = request.query_params.get('division_id')
    if division_id:
        qs = qs.filter(division_id=division_id)

    data = [
        {
            'id': p.id,
            'codigo': p.codigo,
            'nombre': p.nombre,
            'division_id': p.division_id,
            'division_nombre': p.division.nombre if p.division else None,
            'duracion_semestres': p.duracion_semestres,
            'activo': p.activo,
        }
        for p in qs
    ]
    return Response({'programas': data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def crear_programa_view(request):
    """
    Crea un nuevo programa.

    POST /api/admin/catalogos/programas/crear/
    Body:
    {
        "codigo": "ISC",
        "nombre": "Ingeniería en Sistemas Computacionales",
        "division_id": 1,
        "duracion_semestres": 9   // opcional, default 9
    }

    Response:
    {
        "success": true,
        "programa": { ... }
    }
    """
    codigo = request.data.get('codigo', '').strip().upper()
    nombre = request.data.get('nombre', '').strip()
    division_id = request.data.get('division_id')
    duracion_semestres = request.data.get('duracion_semestres', 9)

    if not codigo or not nombre or not division_id:
        return Response(
            {'error': 'Se requieren los campos: codigo, nombre, division_id'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        division = Division.objects.get(id=division_id)
    except Division.DoesNotExist:
        return Response({'error': 'División no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if Programa.objects.filter(codigo=codigo).exists():
        return Response(
            {'error': f'Ya existe un programa con el código {codigo}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    programa = Programa.objects.create(
        codigo=codigo,
        nombre=nombre,
        division=division,
        duracion_semestres=duracion_semestres,
        activo=True,
    )

    Auditoria.objects.create(
        usuario=request.user,
        accion='CREAR_PROGRAMA',
        entidad='programa',
        entidad_id=programa.id,
        detalle={'codigo': programa.codigo, 'nombre': programa.nombre, 'division': division.codigo},
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'programa': {
            'id': programa.id,
            'codigo': programa.codigo,
            'nombre': programa.nombre,
            'division_id': programa.division_id,
            'division_nombre': division.nombre,
            'duracion_semestres': programa.duracion_semestres,
            'activo': programa.activo,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@require_admin
def editar_programa_view(request, programa_id):
    """
    Edita un programa existente.

    PATCH /api/admin/catalogos/programas/<programa_id>/editar/
    Body (todos opcionales):
    {
        "nombre": "Nuevo nombre",
        "division_id": 2,
        "duracion_semestres": 10,
        "activo": false
    }

    Response:
    {
        "success": true,
        "programa": { ... }
    }
    """
    try:
        programa = Programa.objects.select_related('division').get(id=programa_id)
    except Programa.DoesNotExist:
        return Response({'error': 'Programa no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    cambios = {}

    if 'nombre' in request.data:
        cambios['nombre'] = {'anterior': programa.nombre, 'nuevo': request.data['nombre']}
        programa.nombre = request.data['nombre']

    if 'duracion_semestres' in request.data:
        cambios['duracion_semestres'] = {'anterior': programa.duracion_semestres, 'nuevo': request.data['duracion_semestres']}
        programa.duracion_semestres = request.data['duracion_semestres']

    if 'activo' in request.data:
        cambios['activo'] = {'anterior': programa.activo, 'nuevo': request.data['activo']}
        programa.activo = request.data['activo']

    if 'division_id' in request.data:
        try:
            nueva_division = Division.objects.get(id=request.data['division_id'])
        except Division.DoesNotExist:
            return Response({'error': 'División no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        cambios['division'] = {'anterior': programa.division.codigo, 'nuevo': nueva_division.codigo}
        programa.division = nueva_division

    if not cambios:
        return Response({'error': 'No se proporcionaron campos a editar'}, status=status.HTTP_400_BAD_REQUEST)

    programa.save()

    Auditoria.objects.create(
        usuario=request.user,
        accion='EDITAR_PROGRAMA',
        entidad='programa',
        entidad_id=programa.id,
        detalle={'cambios': cambios},
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'programa': {
            'id': programa.id,
            'codigo': programa.codigo,
            'nombre': programa.nombre,
            'division_id': programa.division_id,
            'division_nombre': programa.division.nombre,
            'duracion_semestres': programa.duracion_semestres,
            'activo': programa.activo,
        }
    }, status=status.HTTP_200_OK)
