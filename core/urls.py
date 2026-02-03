# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    login_view, logout_view, register_view,
    me_view, change_password_view, first_login_change_password_view, verify_token_view,
    CustomTokenObtainPairView,
    password_reset_request_view, password_reset_validate_view, password_reset_confirm_view,
    import_csv_view,
    import_docentes_view,
    import_alumnos_view,
    asignar_tutor_view,
    remover_tutor_view,
    my_groups_view,
    analizar_importacion_view,
    ejecutar_importacion_view,
    listar_periodos_view,
    activar_periodo_view,
    desactivar_periodo_view,
    crear_periodo_view,
    obtener_periodo_activo_view,
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
    
    # Cambio de contraseña
    path('auth/change-password/', change_password_view, name='change-password'),
    path('auth/first-login-change-password/', first_login_change_password_view, name='first-login-change-password'),
    
    # Tokens
    path('auth/verify-token/', verify_token_view, name='verify-token'),
    path('auth/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Password Reset
    path('auth/password-reset/request/', password_reset_request_view, name='password-reset-request'),
    path('auth/password-reset/validate/', password_reset_validate_view, name='password-reset-validate'),
    path('auth/password-reset/confirm/', password_reset_confirm_view, name='password-reset-confirm'),
    

    # ========================================
    # ADMINISTRACIÓN - IMPORTACIONES
    # ========================================
    path('admin/import-csv/', import_csv_view, name='import-csv'),
    path('admin/import-grupos-completos/', import_csv_view, name='import-grupos-completos'),
    path('admin/import-docentes/', import_docentes_view, name='import-docentes'),
    path('admin/import-alumnos/', import_alumnos_view, name='import-alumnos'),
       # Importación masiva
    path('admin/importacion/analizar/', analizar_importacion_view   , name='importacion_analizar'),
    path('admin/importacion/ejecutar/', ejecutar_importacion_view, name='importacion_ejecutar'),
    
    # ADMINISTRACIÓN - GESTIÓN
    path('admin/asignar-tutor/', asignar_tutor_view, name='asignar-tutor'),
    path('admin/remover-tutor/', remover_tutor_view, name='remover-tutor'),

    # ADMINISTRACIÓN -GESTIÓN DE PERIODOS
        # Listar todos los periodos (admin)
    path('admin/periodos/', listar_periodos_view, name='listar_periodos'),
        # Crear nuevo periodo (admin)
    path('admin/periodos/crear/', crear_periodo_view, name='crear_periodo'),
        # Activar un periodo específico (admin)
    path('admin/periodos/<int:periodo_id>/activar/', activar_periodo_view, name='activar_periodo'),
        # Desactivar un periodo específico (admin)
    path('admin/periodos/<int:periodo_id>/desactivar/', desactivar_periodo_view, name='desactivar_periodo'),
        # Obtener periodo activo (cualquier usuario autenticado)
    path('periodos/activo/', obtener_periodo_activo_view, name='periodo_activo'),


    # ========================================
    # ACADÉMICO (Tutores)
    # ========================================
    path('academic/my-groups/', my_groups_view, name='my-groups'),

    path('', include(router.urls)),
]