# core/utils/decorators.py
from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from core.models import AlumnoGrupo


def require_alumno(view_func):
    """
    Decorador para requerir que el usuario sea un alumno ACTIVO.
    
    Valida:
    - Que sea alumno
    - Que esté ACTIVO (no BAJA/EGRESADO/INACTIVO)
    - Que tenga inscripción activa en el periodo actual
    
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
        # Verificar que tenga el atributo alumno
        if not hasattr(request.user, 'alumno'):
            return Response(
                {'error': 'Solo alumnos pueden acceder a este endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        alumno = request.user.alumno
        
        # Validar estatus del alumno
        if alumno.estatus == 'BAJA':
            return Response(
                {
                    'error': 'Tu cuenta ha sido dada de baja',
                    'detail': 'Contacta a servicios escolares para más información'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        elif alumno.estatus == 'EGRESADO':
            return Response(
                {
                    'error': 'Ya has egresado del programa',
                    'detail': 'Esta sección es solo para alumnos activos'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        elif alumno.estatus == 'INACTIVO':
            return Response(
                {
                    'error': 'Tu cuenta está inactiva',
                    'detail': 'Contacta a servicios escolares para reactivarla'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verificar inscripción activa en periodo actual
        tiene_inscripcion_activa = AlumnoGrupo.objects.filter(
            alumno=alumno,
            activo=1,
            grupo__activo=1,
            grupo__periodo__activo=1
        ).exists()
        
        if not tiene_inscripcion_activa:
            return Response(
                {
                    'error': 'No estás inscrito en el periodo actual',
                    'detail': 'Contacta a servicios escolares'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Agregar alumno al request para fácil acceso
        request.alumno = alumno
        
        return view_func(request, *args, **kwargs)
    return wrapper


def require_tutor(view_func):
    """
    Decorador para requerir que el usuario sea un tutor ACTIVO.
    
    Valida:
    - Que sea docente
    - Que sea tutor (es_tutor=True)
    - Que esté ACTIVO (no INACTIVO/JUBILADO)
    
    Uso:
        @api_view(['GET'])
        @permission_classes([IsAuthenticated])
        @require_tutor
        def mi_vista(request):
            docente = request.user.docente
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
        
        docente = request.user.docente
        
        # Verificar si es tutor
        if not docente.es_tutor:
            return Response(
                {'error': 'Solo tutores pueden acceder a este endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validar estatus del docente
        if docente.estatus == 'INACTIVO':
            return Response(
                {
                    'error': 'Tu cuenta de docente está inactiva',
                    'detail': 'Contacta a recursos humanos'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        elif docente.estatus == 'JUBILADO':
            return Response(
                {
                    'error': 'Tu cuenta está marcada como jubilado',
                    'detail': 'Contacta a recursos humanos'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Agregar docente al request para fácil acceso
        request.docente = docente
        
        return view_func(request, *args, **kwargs)
    return wrapper


def require_docente(view_func):
    """
    Decorador para requerir que el usuario sea un docente ACTIVO (tutor o no).
    
    Valida:
    - Que sea docente
    - Que esté ACTIVO (no INACTIVO/JUBILADO)
    
    Uso:
        @api_view(['GET'])
        @permission_classes([IsAuthenticated])
        @require_docente
        def mi_vista(request):
            docente = request.user.docente
            # ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Verificar si tiene el atributo docente
        if not hasattr(request.user, 'docente'):
            return Response(
                {'error': 'Solo docentes pueden acceder a este endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        docente = request.user.docente
        
        # Validar estatus del docente
        if docente.estatus != 'ACTIVO':
            return Response(
                {
                    'error': f'Tu cuenta está {docente.estatus.lower()}',
                    'detail': 'Contacta a recursos humanos'
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Agregar docente al request para fácil acceso
        request.docente = docente
        
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
    Decorador para requerir que el usuario sea administrador o tutor ACTIVO.
    
    Uso:
        @api_view(['GET'])
        @permission_classes([IsAuthenticated])
        @require_admin_or_tutor
        def mi_vista(request):
            # Si es tutor: request.docente estará disponible
            # Si es admin: solo request.user
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Verificar si es admin
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Verificar si es tutor activo
        if hasattr(request.user, 'docente'):
            docente = request.user.docente
            
            if not docente.es_tutor:
                return Response(
                    {'error': 'Solo administradores o tutores pueden acceder a este endpoint'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if docente.estatus != 'ACTIVO':
                return Response(
                    {
                        'error': f'Tu cuenta de tutor está {docente.estatus.lower()}',
                        'detail': 'Contacta a recursos humanos'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Agregar docente al request
            request.docente = docente
            return view_func(request, *args, **kwargs)
        
        return Response(
            {'error': 'Solo administradores o tutores pueden acceder a este endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    return wrapper


def require_admin_or_docente(view_func):
    """
    Decorador para requerir que el usuario sea administrador o docente ACTIVO (tutor o no).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Verificar si es admin
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Verificar si es docente activo
        if hasattr(request.user, 'docente'):
            docente = request.user.docente
            
            if docente.estatus != 'ACTIVO':
                return Response(
                    {
                        'error': f'Tu cuenta está {docente.estatus.lower()}',
                        'detail': 'Contacta a recursos humanos'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            request.docente = docente
            return view_func(request, *args, **kwargs)
        
        return Response(
            {'error': 'Solo administradores o docentes pueden acceder a este endpoint'},
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