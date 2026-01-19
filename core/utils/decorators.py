from functools import wraps
from rest_framework.response import Response
from rest_framework import status


def require_alumno(view_func):
    """
    Decorador para requerir que el usuario sea un alumno.
    
    Uso:
        @api_view(['GET'])
        @permission_classes([IsAuthenticated])
        @require_alumno
        def mi_vista(request):
            alumno = request.user.alumno
            # ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'alumno'):
            return Response(
                {'error': 'Solo alumnos pueden acceder a este endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        return view_func(request, *args, **kwargs)
    return wrapper


def require_tutor(view_func):
    """
    Decorador para requerir que el usuario sea un tutor.
    
    Uso:
        @api_view(['GET'])
        @permission_classes([IsAuthenticated])
        @require_tutor
        def mi_vista(request):
            # ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Verificar si tiene el atributo docente
        if not hasattr(request.user, 'docente'):
            return Response(
                {'error': 'Solo tutores pueden acceder a este endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar si es tutor
        docente = request.user.docente
        if not docente.es_tutor:
            return Response(
                {'error': 'Solo tutores pueden acceder a este endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return view_func(request, *args, **kwargs)
    return wrapper


def require_admin(view_func):
    """
    Decorador para requerir que el usuario sea administrador.
    
    Uso:
        @api_view(['POST'])
        @permission_classes([IsAuthenticated])
        @require_admin
        def mi_vista(request):
            # ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {'error': 'Solo administradores pueden acceder a este endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        return view_func(request, *args, **kwargs)
    return wrapper


def require_admin_or_tutor(view_func):
    """
    Decorador para requerir que el usuario sea administrador o tutor.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Verificar si es admin
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Verificar si es tutor
        if hasattr(request.user, 'docente') and request.user.docente.es_tutor:
            return view_func(request, *args, **kwargs)
        
        return Response(
            {'error': 'Solo administradores o tutores pueden acceder a este endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    return wrapper


def log_api_call(view_func):
    """
    Decorador para loggear llamadas a la API (útil para debugging).
    
    Uso:
        @api_view(['POST'])
        @log_api_call
        def mi_vista(request):
            # ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"API Call: {request.method} {request.path} by {request.user}")
        response = view_func(request, *args, **kwargs)
        logger.info(f"Response: {response.status_code}")
        
        return response
    return wrapper