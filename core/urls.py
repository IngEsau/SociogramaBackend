# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    login_view, logout_view, register_view,
    me_view, change_password_view, verify_token_view,
    CustomTokenObtainPairView,
    import_csv_view,
    my_groups_view
)

router = DefaultRouter()

app_name = 'core'

urlpatterns = [
    # ========================================
    # AUTENTICACIÓN
    # ========================================
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/register/', register_view, name='register'),
    path('auth/me/', me_view, name='me'),
    path('auth/change-password/', change_password_view, name='change-password'),
    path('auth/verify-token/', verify_token_view, name='verify-token'),
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    

    # ========================================
    # ADMINISTRACIÓN
    # ========================================
    path('admin/import-csv/', import_csv_view, name='import-csv'),


    # ========================================
    # ACADÉMICO (Tutores)
    # ========================================
    path('academic/my-groups/', my_groups_view, name='my-groups'),

    path('', include(router.urls)),
]