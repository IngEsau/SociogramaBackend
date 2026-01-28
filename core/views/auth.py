# core/views/auth.py
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from core.models import User, Alumno, Docente
from core.utils.email import send_password_reset_email
from ..serializers import (
    LoginSerializer, RegisterSerializer, UserSerializer, AlumnoSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer
)


# ============================================
# CUSTOM TOKEN SERIALIZER
# ============================================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializador personalizado para incluir info adicional en el token"""
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Agregar información del User extendido
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'nombre_completo': self.user.nombre_completo or self.user.get_full_name(), 
            'rol': self.user.rol,  
            'genero': self.user.genero,  
            'is_staff': self.user.is_staff,
        }
        
        # Si es alumno, agregar info del alumno
        if self.user.rol == 'ALUMNO':  
            try:
                alumno = Alumno.objects.get(user=self.user)
                data['user']['alumno'] = {
                    'id': alumno.id,
                    'matricula': alumno.matricula,
                    'semestre': alumno.semestre_actual,
                    'estatus': alumno.estatus,
                }
            except Alumno.DoesNotExist:
                pass
        
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# ============================================
# ENDPOINTS DE AUTENTICACIÓN
# ============================================

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Endpoint para login con username/matrícula y password
    
    POST /api/auth/login/
    Body: {
        "username": "matricula_o_username",
        "password": "contraseña"
    }
    
    Response: {
        "access": "token_de_acceso",
        "refresh": "token_de_refresh",
        "first_login": true/false,  # Indica si es primer login
        "user": {...}
    }
    """
    serializer = LoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)

        # Preparar respuesta con campos del User extendido
        response_data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'first_login': user.last_login is None,  # Detectar primer login
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'nombre_completo': user.nombre_completo or user.get_full_name(),
                'first_name': user.first_name,
                'last_name': user.last_name,
                'rol': user.rol,
                'genero': user.genero,
                'is_staff': user.is_staff,
            }
        }

        # CAMBIO: Usar el campo rol para determinar el tipo de usuario
        if user.rol == 'ALUMNO':
            try:
                alumno = Alumno.objects.select_related('plan_estudio__programa').get(user=user)
                response_data['user']['alumno'] = {
                    'id': alumno.id,
                    'matricula': alumno.matricula,
                    'semestre_actual': alumno.semestre_actual,
                    'promedio': float(alumno.promedio) if alumno.promedio else None,
                    'estatus': alumno.estatus,
                    'programa': alumno.plan_estudio.programa.nombre if alumno.plan_estudio else None,
                }
            except Alumno.DoesNotExist:
                pass
        
        elif user.rol == 'DOCENTE':
            try:
                docente = Docente.objects.select_related('division').get(user=user)
                response_data['user']['docente'] = {
                    'id': docente.id,
                    'profesor_id': docente.profesor_id,
                    'es_tutor': docente.es_tutor,
                    'division': docente.division.nombre if docente.division else None,
                }
            except Docente.DoesNotExist:
                pass
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Endpoint para logout (blacklist del refresh token)
    
    POST /api/auth/logout/
    Body: {
        "refresh": "refresh_token"
    }
    """
    try:
        refresh_token = request.data.get('refresh')
        
        if not refresh_token:
            return Response(
                {'error': 'Refresh token es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response(
            {'message': 'Logout exitoso'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """
    Endpoint para registro de nuevos usuarios
    
    POST /api/auth/register/
    Body: {
        "username": "usuario",
        "email": "correo@example.com",
        "password": "contraseña",
        "password2": "contraseña",
        "first_name": "Nombre",
        "last_name": "Apellido",
        "rol": "ALUMNO",  // ALUMNO, DOCENTE, ADMIN
        "genero": "Masculino"  // Masculino, Femenino, Otro
    }
    """
    serializer = RegisterSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        # Generar tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Usuario registrado exitosamente',
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    Endpoint para obtener información del usuario autenticado
    
    GET /api/auth/me/
    
    Response: {
        "user": {...},
        "alumno": {...}  // Si es alumno
        "docente": {...}  // Si es docente
    }
    """
    user = request.user
    response_data = {
        'user': UserSerializer(user).data,
        'rol': user.rol  # Campo directo
    }

    # CAMBIO: Usar el campo rol para determinar el tipo de usuario
    if user.rol == 'ALUMNO':
        try:
            alumno = Alumno.objects.select_related(
                'plan_estudio__programa__division'
            ).get(user=user)
            response_data['alumno'] = AlumnoSerializer(alumno).data
        except Alumno.DoesNotExist:
            pass
    
    elif user.rol == 'DOCENTE':
        try:
            docente = Docente.objects.select_related('division').get(user=user)
            response_data['docente'] = {
                'id': docente.id,
                'profesor_id': docente.profesor_id,
                'es_tutor': docente.es_tutor,
                'division': docente.division.nombre if docente.division else None,
                'especialidad': docente.especialidad,
                'estatus': docente.estatus,
            }
            
            # Si es tutor, agregar grupos
            if docente.es_tutor:
                response_data['grupos'] = list(
                    docente.grupos_tutor.filter(activo=True).values(
                        'id', 'clave', 'grado', 'grupo'
                    )
                )
        except Docente.DoesNotExist:
            pass
    
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """
    Endpoint para cambiar contraseña (USUARIOS REGULARES)
    
    POST /api/auth/change-password/
    Body: {
        "old_password": "contraseña_actual",
        "new_password": "contraseña_nueva",
        "new_password2": "contraseña_nueva"
    }
    
    NOTA: Para primer login, usar /api/auth/first-login-change-password/
    """
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    new_password2 = request.data.get('new_password2')
    
    # Validaciones
    if not all([old_password, new_password, new_password2]):
        return Response(
            {'error': 'Todos los campos son requeridos'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not user.check_password(old_password):
        return Response(
            {'error': 'Contraseña actual incorrecta'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if new_password != new_password2:
        return Response(
            {'error': 'Las contraseñas nuevas no coinciden'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(new_password) < 8:
        return Response(
            {'error': 'La contraseña debe tener al menos 8 caracteres'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Cambiar contraseña
    user.set_password(new_password)
    user.save()
    
    return Response(
        {'message': 'Contraseña actualizada exitosamente'},
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def first_login_change_password_view(request):
    """
    Endpoint para cambiar contraseña en el PRIMER LOGIN
    
    POST /api/auth/first-login-change-password/
    Body: {
        "new_password": "contraseña_nueva",
        "new_password2": "contraseña_nueva"
    }
    
    Este endpoint:
    - Solo funciona si last_login es NULL (primer login)
    - NO requiere contraseña antigua
    - Actualiza last_login automáticamente
    - Marca que el usuario ya no está en primer login
    
    Response: {
        "message": "Contraseña actualizada exitosamente",
        "first_login_completed": true
    }
    """
    user = request.user
    
    # VALIDACIÓN 1: Verificar que sea primer login
    if user.last_login is not None:
        return Response(
            {
                'error': 'Este endpoint solo está disponible para el primer login',
                'detail': 'Use /api/auth/change-password/ para cambiar su contraseña'
            },
            status=status.HTTP_403_FORBIDDEN
        )
    
    # VALIDACIÓN 2: Obtener datos
    new_password = request.data.get('new_password')
    new_password2 = request.data.get('new_password2')
    
    if not all([new_password, new_password2]):
        return Response(
            {'error': 'Todos los campos son requeridos'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # VALIDACIÓN 3: Verificar que coincidan
    if new_password != new_password2:
        return Response(
            {'error': 'Las contraseñas no coinciden'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # VALIDACIÓN 4: Longitud mínima
    if len(new_password) < 8:
        return Response(
            {'error': 'La contraseña debe tener al menos 8 caracteres'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # VALIDACIÓN 5: No puede ser igual a la contraseña temporal
    if user.check_password(new_password):
        return Response(
            {'error': 'La nueva contraseña no puede ser igual a la contraseña temporal'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # ACTUALIZAR contraseña
    user.set_password(new_password)
    
    # IMPORTANTE: Actualizar last_login para marcar que ya no es primer login
    user.last_login = timezone.now()
    user.save()
    
    return Response(
        {
            'message': 'Contraseña actualizada exitosamente',
            'first_login_completed': True,
            'detail': 'Ahora puede usar el sistema normalmente'
        },
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_token_view(request):
    """
    Endpoint para verificar si un token es válido
    
    POST /api/auth/verify-token/
    Body: {
        "token": "access_token"
    }
    """
    from rest_framework_simplejwt.tokens import AccessToken
    
    token = request.data.get('token')
    
    if not token:
        return Response(
            {'error': 'Token es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        AccessToken(token)
        return Response(
            {'valid': True, 'message': 'Token válido'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'valid': False, 'error': str(e)},
            status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request_view(request):
    """
    Endpoint para solicitar reset de contraseña
    
    POST /api/auth/password-reset/request/
    Body: {
        "email": "usuario@example.com"
    }
    
    Response: {
        "message": "Si el correo existe, recibirás instrucciones para restablecer tu contraseña"
    }
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email, is_active=True)
            
            # Generar token JWT especial para reset
            refresh = RefreshToken.for_user(user)
            
            # Agregar claim personalizado
            refresh['type'] = 'password_reset'
            
            # Token de acceso con expiración de 1 hora
            access_token = refresh.access_token
            access_token.set_exp(lifetime=timedelta(hours=1))
            
            reset_token = str(access_token)
            
            # Guardar el token en OutstandingToken para poder invalidarlo después
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
            from django.utils import timezone
            
            OutstandingToken.objects.create(
                user_id=user.id,
                jti=access_token['jti'],
                token=reset_token,
                created_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=1)
            )
            
            # Enviar correo
            send_password_reset_email(
                user_email=user.email,
                reset_token=reset_token,
                user_name=user.nombre_completo or user.get_full_name()
            )
            
        except User.DoesNotExist:
            # Por seguridad, no revelamos si el email existe
            pass
        
        # Siempre retornamos el mismo mensaje
        return Response({
            'message': 'Si el correo existe, recibirás instrucciones para restablecer tu contraseña'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_validate_view(request):
    """
    Endpoint para validar token de reset
    
    POST /api/auth/password-reset/validate/
    Body: {
        "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
    }
    
    Response: {
        "valid": true,
        "message": "Token válido"
    }
    """
    token = request.data.get('token')
    
    if not token:
        return Response(
            {'error': 'Token es requerido'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Decodificar token
        access_token = AccessToken(token)
        
        # Verificar que sea un token de tipo password_reset
        if access_token.get('type') != 'password_reset':
            return Response(
                {'valid': False, 'error': 'Token inválido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificar que el usuario exista y esté activo
        user_id = access_token.get('user_id')
        user = User.objects.get(id=user_id, is_active=True)
        
        return Response({
            'valid': True,
            'message': 'Token válido',
            'email': user.email  # Para mostrar en el frontend
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'valid': False, 'error': 'Token inválido o expirado'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm_view(request):
    """
    Endpoint para confirmar reset de contraseña
    
    POST /api/auth/password-reset/confirm/
    Body: {
        "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
        "new_password": "nueva_contraseña",
        "new_password2": "nueva_contraseña"
    }
    
    Response: {
        "message": "Contraseña actualizada exitosamente"
    }
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if serializer.is_valid():
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            # Decodificar y validar token
            access_token = AccessToken(token)
            
            # Verificar que sea token de password_reset
            if access_token.get('type') != 'password_reset':
                return Response(
                    {'error': 'Token inválido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verificar si el token ya está en blacklist
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
            
            jti = access_token.get('jti')
            outstanding_token = OutstandingToken.objects.filter(jti=jti).first()
            
            if not outstanding_token:
                return Response(
                    {'error': 'Token inválido'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verificar si ya está en blacklist
            if BlacklistedToken.objects.filter(token=outstanding_token).exists():
                return Response(
                    {'error': 'Token ya ha sido utilizado'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Obtener usuario
            user_id = access_token.get('user_id')
            user = User.objects.get(id=user_id, is_active=True)
            
            # Actualizar contraseña
            user.set_password(new_password)
            user.save()
            
            # Agregar token al blacklist
            BlacklistedToken.objects.create(token=outstanding_token)
            
            return Response({
                'message': 'Contraseña actualizada exitosamente'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response(
                {'error': 'Usuario no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': 'Token inválido o expirado'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)