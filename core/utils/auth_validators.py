# core/utils/auth_validators.py
"""
Validadores y serializadores personalizados para autenticación
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from core.models import Alumno, Docente, AlumnoGrupo


# ============================================
# VALIDACIÓN DE ESTATUS ACTIVO
# ============================================

def validate_user_active_status(user):
    """
    Valida que un usuario esté activo según su rol.
    
    Valida:
    - Alumnos: estatus ACTIVO + inscripción en periodo actual
    - Docentes: estatus ACTIVO (no INACTIVO/JUBILADO)
    - Admins: siempre válidos
    
    Args:
        user: Instancia de User
        
    Returns:
        tuple: (is_valid: bool, error_response: Response or None)
        
    Examples:
        >>> is_valid, error = validate_user_active_status(user)
        >>> if not is_valid:
        >>>     return error
    """
    if user.rol == 'ALUMNO':
        try:
            alumno = Alumno.objects.get(user=user)
            
            # Validar estatus del alumno
            if alumno.estatus == 'BAJA':
                return False, Response(
                    {
                        'error': 'Tu cuenta ha sido dada de baja',
                        'detail': 'Contacta a servicios escolares para más información'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            elif alumno.estatus == 'EGRESADO':
                return False, Response(
                    {
                        'error': 'Ya has egresado del programa',
                        'detail': 'Esta sección es solo para alumnos activos'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            elif alumno.estatus == 'INACTIVO':
                return False, Response(
                    {
                        'error': 'Tu cuenta está inactiva',
                        'detail': 'Contacta a servicios escolares para reactivarla'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Validar inscripción activa en periodo actual
            tiene_inscripcion = AlumnoGrupo.objects.filter(
                alumno=alumno,
                activo=1,
                grupo__activo=1,
                grupo__periodo__activo=1
            ).exists()
            
            if not tiene_inscripcion:
                return False, Response(
                    {
                        'error': 'No estás inscrito en el periodo actual',
                        'detail': 'Contacta a servicios escolares'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
                
        except Alumno.DoesNotExist:
            return False, Response(
                {'error': 'No se encontró registro de alumno'},
                status=status.HTTP_403_FORBIDDEN
            )
    
    elif user.rol == 'DOCENTE':
        try:
            docente = Docente.objects.get(user=user)
            
            # Validar estatus del docente
            if docente.estatus == 'INACTIVO':
                return False, Response(
                    {
                        'error': 'Tu cuenta de docente está inactiva',
                        'detail': 'Contacta a recursos humanos'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            elif docente.estatus == 'JUBILADO':
                return False, Response(
                    {
                        'error': 'Tu cuenta está marcada como jubilado',
                        'detail': 'Contacta a recursos humanos'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
                
        except Docente.DoesNotExist:
            return False, Response(
                {'error': 'No se encontró registro de docente'},
                status=status.HTTP_403_FORBIDDEN
            )
    
    # Si pasa todas las validaciones (o es ADMIN)
    return True, None


# ============================================
# CUSTOM TOKEN SERIALIZER
# ============================================

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializador personalizado para incluir información adicional en el token.
    
    Incluye en la respuesta:
    - Datos básicos del usuario
    - Rol del usuario
    - Información del alumno (si es alumno)
    - Información del docente (si es docente)
    """
    
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
    """Vista personalizada que usa CustomTokenObtainPairSerializer"""
    serializer_class = CustomTokenObtainPairSerializer