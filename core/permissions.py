# core/permissions.py
from rest_framework import permissions


class IsAlumno(permissions.BasePermission):
    """
    Permiso: Solo usuarios que son alumnos pueden acceder
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'alumno')


class IsTutor(permissions.BasePermission):
    """
    Permiso: Solo usuarios que son tutores pueden acceder
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.grupos_tutor.exists()


class IsAdminOrTutor(permissions.BasePermission):
    """
    Permiso: Administradores o tutores pueden acceder
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_staff or request.user.grupos_tutor.exists()


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permiso: Solo el dueño del objeto o un administrador pueden acceder
    Usado a nivel de objeto (has_object_permission)
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin puede todo
        if request.user.is_staff:
            return True
        
        # Si el objeto tiene un campo 'alumno', verificar que sea el dueño
        if hasattr(obj, 'alumno'):
            return hasattr(request.user, 'alumno') and obj.alumno == request.user.alumno
        
        # Si el objeto tiene un campo 'user', verificar que sea el dueño
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class CanViewGrupo(permissions.BasePermission):
    """
    Permiso: Puede ver el grupo si es:
    - Administrador
    - Tutor del grupo
    - Alumno inscrito en el grupo
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin puede ver todo
        if request.user.is_staff:
            return True
        
        # Tutor del grupo puede ver
        if obj.tutor == request.user:
            return True
        
        # Alumno del grupo puede ver
        if hasattr(request.user, 'alumno'):
            return obj.alumnos.filter(
                alumno=request.user.alumno, 
                activo=True
            ).exists()
        
        return False


class CanEditGrupo(permissions.BasePermission):
    """
    Permiso: Puede editar el grupo si es:
    - Administrador
    - Tutor del grupo
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin puede editar todo
        if request.user.is_staff:
            return True
        
        # Tutor del grupo puede editar
        if obj.tutor == request.user:
            return True
        
        return False


class IsAlumnoOrReadOnly(permissions.BasePermission):
    """
    Permiso: Los alumnos pueden leer, pero solo admin/tutores pueden escribir
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Métodos de lectura permitidos para alumnos
        if request.method in permissions.SAFE_METHODS:
            return hasattr(request.user, 'alumno')
        
        # Escritura solo para admin o tutores
        return request.user.is_staff or request.user.grupos_tutor.exists()


class CanAnswerSurvey(permissions.BasePermission):
    """
    Permiso: Solo alumnos pueden responder encuestas
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'alumno')


class CanViewReports(permissions.BasePermission):
    """
    Permiso: Administradores y tutores pueden ver reportes
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.is_staff or request.user.grupos_tutor.exists()
    
    def has_object_permission(self, request, view, obj):
        # Admin puede ver todos los reportes
        if request.user.is_staff:
            return True
        
        # Tutor solo puede ver reportes de sus grupos
        if hasattr(obj, 'grupo'):
            return obj.grupo.tutor == request.user
        
        return False