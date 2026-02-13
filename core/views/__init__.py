# core/views/__init__.py
"""
Views del Sistema Sociograma UTP
Exporta todos los endpoints de la aplicación
"""

# Views de autenticación
from .auth import (
    login_view,
    logout_view,
    register_view,
    me_view,
    change_password_view,
    verify_token_view,
    CustomTokenObtainPairView,
    password_reset_request_view,
    password_reset_validate_view,
    password_reset_confirm_view,
    first_login_change_password_view,
)

# Views de administración
from .admin import (
    import_csv_view,
    import_docentes_view,
    import_alumnos_view,
    asignar_tutor_view,
    remover_tutor_view,
    analizar_importacion_view,
    ejecutar_importacion_view,
    listar_periodos_view,
    activar_periodo_view,
    desactivar_periodo_view,
    crear_periodo_view,
    obtener_periodo_activo_view,
)

# Views académicas
try:
    from .academic.academic import (
        my_groups_view,
    )
except ImportError:
    my_groups_view = None

__all__ = [
    # Autenticación
    'login_view',
    'logout_view',
    'register_view',
    'me_view',
    'change_password_view',
    'verify_token_view',
    'CustomTokenObtainPairView',
    'password_reset_request_view',
    'password_reset_validate_view',
    'password_reset_confirm_view',
    'first_login_change_password_view',
    
    # Administración
    'import_csv_view',
    'import_docentes_view',
    'import_alumnos_view',
    'asignar_tutor_view',
    'remover_tutor_view',
    'analizar_importacion_view',
    'ejecutar_importacion_view',

    # Administración de Periodos
    'listar_periodos_view',
    'activar_periodo_view',
    'desactivar_periodo_view',
    'crear_periodo_view',
    'obtener_periodo_activo_view',
    
    # Académico
    'my_groups_view',
]