from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from core.models import User, Alumno, Docente
from ..serializers import (
    LoginSerializer, RegisterSerializer, UserSerializer, AlumnoSerializer
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
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'nombre_completo': user.nombre_completo or user.get_full_name(),  # Campo directo
                'first_name': user.first_name,
                'last_name': user.last_name,
                'rol': user.rol,  # Campo directo
                'genero': user.genero,  # Campo directo
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
    Endpoint para cambiar contraseña
    
    POST /api/auth/change-password/
    Body: {
        "old_password": "contraseña_actual",
        "new_password": "contraseña_nueva",
        "new_password2": "contraseña_nueva"
    }
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