# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    login_view, logout_view, register_view,
    me_view, change_password_view, verify_token_view,
    CustomTokenObtainPairView,
    import_csv_view,
    import_docentes_view,
    import_alumnos_view,
    asignar_tutor_view,
    remover_tutor_view,
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
    # ADMINISTRACIÓN - IMPORTACIONES
    # ========================================
    path('admin/import-csv/', import_csv_view, name='import-csv'),
    path('admin/import-grupos-completos/', import_csv_view, name='import-grupos-completos'),  # Alias más claro
    path('admin/import-docentes/', import_docentes_view, name='import-docentes'),
    path('admin/import-alumnos/', import_alumnos_view, name='import-alumnos'),
    
    # ADMINISTRACIÓN - GESTIÓN
    path('admin/asignar-tutor/', asignar_tutor_view, name='asignar-tutor'),
    path('admin/remover-tutor/', remover_tutor_view, name='remover-tutor'),


    # ========================================
    # ACADÉMICO (Tutores)
    # ========================================
    path('academic/my-groups/', my_groups_view, name='my-groups'),

    path('', include(router.urls)),
]