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
)

# Views de administración
from .admin import (
    import_csv_view,
)

# Views académicas (si existen)
try:
    from .academic import (
        my_groups_view,
    )
except ImportError:
    # Si no existe el archivo academic.py todavía
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
    
    # Administración
    'import_csv_view',
    
    # Académico
    'my_groups_view',
]