# core/views/admin/usuarios.py
"""
Endpoints CRUD de Usuarios (mínimo)
crear / editar / activar / desactivar
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from core.models import User, Auditoria
from core.utils.decorators import require_admin


def _get_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_admin
def listar_usuarios_view(request):
    """
    Lista usuarios con filtros opcionales.

    GET /api/admin/usuarios/
    Query params:
        - rol: ALUMNO | DOCENTE | ADMIN | COMITE
        - activo: true | false
        - q: búsqueda por nombre, username o email

    Response:
    {
        "usuarios": [
            {
                "id": 1,
                "username": "john",
                "nombre_completo": "John Doe",
                "email": "john@example.com",
                "rol": "ALUMNO",
                "is_active": true,
                "is_staff": false
            }
        ],
        "total": 1
    }
    """
    qs = User.objects.all().order_by('rol', 'nombre_completo')

    rol = request.query_params.get('rol')
    if rol:
        qs = qs.filter(rol=rol)

    activo = request.query_params.get('activo')
    if activo is not None:
        qs = qs.filter(is_active=(activo.lower() == 'true'))

    q = request.query_params.get('q')
    if q:
        qs = qs.filter(
            Q(nombre_completo__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q)
        )

    usuarios = [
        {
            'id': u.id,
            'username': u.username,
            'nombre_completo': u.nombre_completo or u.get_full_name(),
            'email': u.email,
            'rol': u.rol,
            'is_active': u.is_active,
            'is_staff': u.is_staff,
        }
        for u in qs
    ]

    return Response({'usuarios': usuarios, 'total': len(usuarios)}, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@require_admin
def editar_usuario_view(request, usuario_id):
    """
    Edita datos básicos de un usuario.

    PATCH /api/admin/usuarios/<usuario_id>/editar/
    Body (todos opcionales):
    {
        "nombre_completo": "Nuevo Nombre",
        "email": "nuevo@email.com",
        "telefono": "2222222222",
        "rol": "DOCENTE"
    }

    Response:
    {
        "success": true,
        "usuario": { ... }
    }
    """
    try:
        usuario = User.objects.get(id=usuario_id)
    except User.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    CAMPOS_EDITABLES = ['nombre_completo', 'email', 'telefono', 'rol']
    cambios = {}

    for campo in CAMPOS_EDITABLES:
        if campo in request.data:
            valor_anterior = getattr(usuario, campo)
            setattr(usuario, campo, request.data[campo])
            cambios[campo] = {'anterior': str(valor_anterior), 'nuevo': str(request.data[campo])}

    if not cambios:
        return Response({'error': 'No se proporcionaron campos a editar'}, status=status.HTTP_400_BAD_REQUEST)

    usuario.save()

    Auditoria.objects.create(
        usuario=request.user,
        accion='EDITAR_USUARIO',
        entidad='usuario',
        entidad_id=usuario.id,
        detalle={'cambios': cambios},
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'usuario': {
            'id': usuario.id,
            'username': usuario.username,
            'nombre_completo': usuario.nombre_completo,
            'email': usuario.email,
            'rol': usuario.rol,
            'is_active': usuario.is_active,
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def activar_usuario_view(request, usuario_id):
    """
    Activa un usuario (is_active = True).

    POST /api/admin/usuarios/<usuario_id>/activar/

    Response:
    {
        "success": true,
        "usuario": { "id": 1, "username": "john", "is_active": true }
    }
    """
    try:
        usuario = User.objects.get(id=usuario_id)
    except User.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if usuario.is_active:
        return Response({'error': 'El usuario ya está activo'}, status=status.HTTP_400_BAD_REQUEST)

    usuario.is_active = True
    usuario.save(update_fields=['is_active'])

    Auditoria.objects.create(
        usuario=request.user,
        accion='ACTIVAR_USUARIO',
        entidad='usuario',
        entidad_id=usuario.id,
        detalle={'username': usuario.username},
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'usuario': {'id': usuario.id, 'username': usuario.username, 'is_active': True}
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def desactivar_usuario_view(request, usuario_id):
    """
    Desactiva un usuario (is_active = False).
    No se permite desactivar al propio usuario que hace la petición.

    POST /api/admin/usuarios/<usuario_id>/desactivar/

    Response:
    {
        "success": true,
        "usuario": { "id": 1, "username": "john", "is_active": false }
    }
    """
    try:
        usuario = User.objects.get(id=usuario_id)
    except User.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if usuario.id == request.user.id:
        return Response({'error': 'No puedes desactivar tu propia cuenta'}, status=status.HTTP_400_BAD_REQUEST)

    if not usuario.is_active:
        return Response({'error': 'El usuario ya está inactivo'}, status=status.HTTP_400_BAD_REQUEST)

    usuario.is_active = False
    usuario.save(update_fields=['is_active'])

    Auditoria.objects.create(
        usuario=request.user,
        accion='DESACTIVAR_USUARIO',
        entidad='usuario',
        entidad_id=usuario.id,
        detalle={'username': usuario.username},
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'usuario': {'id': usuario.id, 'username': usuario.username, 'is_active': False}
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def crear_usuario_view(request):
    """
    Crea un usuario manualmente desde el panel de admin.

    POST /api/admin/usuarios/crear/
    Body:
    {
        "username":   "jgarcia",
        "first_name": "Juan",
        "last_name":  "García López",
        "email":      "jgarcia@utp.edu.mx",
        "rol":        "DOCENTE",          // ALUMNO | DOCENTE | ADMIN | COMITE
        "password":   "pass1234"          // opcional — default: username
    }

    Notas:
    - ADMIN: is_staff=True automáticamente.
    - ALUMNO: is_active=False hasta que se asigne a un grupo del periodo activo.
    - Si no se envía password, se usa el username como contraseña temporal.

    Response 201:
    {
        "success": true,
        "usuario": {
            "id": 10,
            "username": "jgarcia",
            "nombre_completo": "Juan García López",
            "email": "jgarcia@utp.edu.mx",
            "rol": "DOCENTE",
            "is_active": true,
            "is_staff": false
        }
    }
    """
    ROLES_VALIDOS = ['ALUMNO', 'DOCENTE', 'ADMIN', 'COMITE']

    username   = request.data.get('username', '').strip()
    first_name = request.data.get('first_name', '').strip()
    last_name  = request.data.get('last_name', '').strip()
    email      = request.data.get('email', '').strip()
    rol        = request.data.get('rol', '').upper().strip()
    password   = request.data.get('password', '').strip() or username

    if not username or not first_name or not last_name or not rol:
        return Response(
            {'error': 'Se requieren: username, first_name, last_name, rol'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if rol not in ROLES_VALIDOS:
        return Response(
            {'error': f'Rol inválido. Opciones: {", ".join(ROLES_VALIDOS)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if User.objects.filter(username=username).exists():
        return Response(
            {'error': f'Ya existe un usuario con username "{username}"'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Flags según rol
    is_staff    = rol == 'ADMIN'
    # Alumnos inactivos hasta tener inscripción; los demás activos desde el inicio
    is_active   = rol != 'ALUMNO'

    usuario = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        rol=rol,
        is_staff=is_staff,
        is_active=is_active,
    )
    usuario.set_password(password)
    usuario.save()  # save() auto-llena nombre_completo con first+last

    Auditoria.objects.create(
        usuario=request.user,
        accion='CREAR_USUARIO',
        entidad='usuario',
        entidad_id=usuario.id,
        detalle={
            'username': usuario.username,
            'rol': usuario.rol,
            'password_temporal': password == username,
        },
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'usuario': {
            'id': usuario.id,
            'username': usuario.username,
            'nombre_completo': usuario.nombre_completo,
            'email': usuario.email,
            'rol': usuario.rol,
            'is_active': usuario.is_active,
            'is_staff': usuario.is_staff,
        }
    }, status=status.HTTP_201_CREATED)
