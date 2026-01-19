# core/views/__init__.py
from .auth import (
    login_view,
    logout_view,
    register_view,
    me_view,
    change_password_view,
    verify_token_view,
    CustomTokenObtainPairView
)
from .admin import import_csv_view
from .academic import my_groups_view

__all__ = [
    # Auth
    'login_view',
    'logout_view',
    'register_view',
    'me_view',
    'change_password_view',
    'verify_token_view',
    'CustomTokenObtainPairView',
    
    # Admin
    'import_csv_view',
    
    # Academic
    'my_groups_view',
]