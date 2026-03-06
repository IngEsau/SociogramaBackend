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
    editar_periodo_view,
    listar_usuarios_view,
    crear_usuario_view,
    editar_usuario_view,
    activar_usuario_view,
    desactivar_usuario_view,
    crear_grupo_view,
    editar_tutor_grupo_view,
    listar_divisiones_view,
    crear_division_view,
    editar_division_view,
    listar_programas_view,
    crear_programa_view,
    editar_programa_view,
)

# Importar views de cuestionarios admin
from .views.admin.cuestionarios import (
    crear_cuestionario_view,
    listar_cuestionarios_view,
    detalle_cuestionario_view,
    actualizar_cuestionario_view,
    eliminar_cuestionario_view,
    activar_cuestionario_view,
    desactivar_cuestionario_view,
    agregar_pregunta_view,
    remover_pregunta_view,
    asociar_pregunta_view,
)

# Importar views de preguntas admin
from .views.admin.preguntas import (
    listar_preguntas_view,
    crear_pregunta_view,
    detalle_pregunta_view,
    actualizar_pregunta_view,
    eliminar_pregunta_view,
    editar_copia_view,
)

# Importar views de COMITÉ
from .views.comite.cuestionarios import (
    listar_cuestionarios_comite_view,
    detalle_cuestionario_comite_view,
    progreso_cuestionario_comite_view,
    estadisticas_cuestionario_comite_view,
)

from .views.comite.dashboard import (
    overview_comite_view,
    graphs_comite_view,
    progreso_overview_comite_view,
    alertas_comite_view,
    centralidad_comite_view,
)

# Importar views de cuestionarios tutores
from .views.academic.cuestionarios import (
    listar_cuestionarios_tutor_view,
    detalle_cuestionario_tutor_view,
    progreso_cuestionario_view,
    estadisticas_cuestionario_view,
    registro_cuestionario_view,
    clasificacion_por_pregunta_view,
)

# Importar views de exportación (archivos)
from .views.academic.archivos import (
    listar_cuestionarios_historico_view,
    datos_sociograma_view,
    exportar_csv_view,
    exportar_pdf_view,
)

from .views.student.cuestionarios import (
    cuestionarios_disponibles_view,
    detalle_cuestionario_alumno_view,
    preguntas_cuestionario_view,
    iniciar_cuestionario_view,
    responder_cuestionario_view,
    mi_progreso_view,
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
    path('admin/importacion/analizar/', analizar_importacion_view, name='importacion_analizar'),
    path('admin/importacion/ejecutar/', ejecutar_importacion_view, name='importacion_ejecutar'),
    
    # ========================================
    # ADMINISTRACIÓN - GESTIÓN
    # ========================================
    path('admin/asignar-tutor/', asignar_tutor_view, name='asignar-tutor'),
    path('admin/remover-tutor/', remover_tutor_view, name='remover-tutor'),

    # ========================================
    # ADMINISTRACIÓN - GESTIÓN DE PERIODOS
    # ========================================
    path('admin/periodos/', listar_periodos_view, name='listar_periodos'),
    path('admin/periodos/crear/', crear_periodo_view, name='crear_periodo'),
    path('admin/periodos/<int:periodo_id>/activar/', activar_periodo_view, name='activar_periodo'),
    path('admin/periodos/<int:periodo_id>/desactivar/', desactivar_periodo_view, name='desactivar_periodo'),
    path('admin/periodos/<int:periodo_id>/editar/', editar_periodo_view, name='editar_periodo'),
    path('periodos/activo/', obtener_periodo_activo_view, name='periodo_activo'),

    # ========================================
    # ADMINISTRACIÓN - GESTIÓN DE USUARIOS
    # ========================================
    path('admin/usuarios/', listar_usuarios_view, name='listar_usuarios'),
    path('admin/usuarios/crear/', crear_usuario_view, name='crear_usuario'),
    path('admin/usuarios/<int:usuario_id>/editar/', editar_usuario_view, name='editar_usuario'),
    path('admin/usuarios/<int:usuario_id>/activar/', activar_usuario_view, name='activar_usuario'),
    path('admin/usuarios/<int:usuario_id>/desactivar/', desactivar_usuario_view, name='desactivar_usuario'),

    # ========================================
    # ADMINISTRACIÓN - GESTIÓN DE GRUPOS
    # ========================================
    path('admin/grupos/crear/', crear_grupo_view, name='crear_grupo'),
    path('admin/grupos/<int:grupo_id>/editar-tutor/', editar_tutor_grupo_view, name='editar_tutor_grupo'),

    # ========================================
    # ADMINISTRACIÓN - CATÁLOGOS
    # ========================================
    path('admin/catalogos/divisiones/', listar_divisiones_view, name='listar_divisiones'),
    path('admin/catalogos/divisiones/crear/', crear_division_view, name='crear_division'),
    path('admin/catalogos/divisiones/<int:division_id>/editar/', editar_division_view, name='editar_division'),
    path('admin/catalogos/programas/', listar_programas_view, name='listar_programas'),
    path('admin/catalogos/programas/crear/', crear_programa_view, name='crear_programa'),
    path('admin/catalogos/programas/<int:programa_id>/editar/', editar_programa_view, name='editar_programa'),

    # ========================================
    # ADMINISTRACIÓN - GESTIÓN DE CUESTIONARIOS
    # ========================================
    path('admin/cuestionarios/crear/', crear_cuestionario_view, name='crear_cuestionario'),
    path('admin/cuestionarios/', listar_cuestionarios_view, name='listar_cuestionarios'),
    path('admin/cuestionarios/<int:cuestionario_id>/', detalle_cuestionario_view, name='detalle_cuestionario'),
    path('admin/cuestionarios/<int:cuestionario_id>/actualizar/', actualizar_cuestionario_view, name='actualizar_cuestionario'),
    path('admin/cuestionarios/<int:cuestionario_id>/eliminar/', eliminar_cuestionario_view, name='eliminar_cuestionario'),
    path('admin/cuestionarios/<int:cuestionario_id>/activar/', activar_cuestionario_view, name='activar_cuestionario'),
    path('admin/cuestionarios/<int:cuestionario_id>/desactivar/', desactivar_cuestionario_view, name='desactivar_cuestionario'),
    path('admin/cuestionarios/<int:cuestionario_id>/agregar-pregunta/', agregar_pregunta_view, name='agregar_pregunta'),
    path('admin/cuestionarios/<int:cuestionario_id>/remover-pregunta/<int:pregunta_id>/', remover_pregunta_view, name='remover_pregunta'),
    path('admin/cuestionarios/<int:cuestionario_id>/asociar-pregunta/', asociar_pregunta_view, name='asociar_pregunta'),

    # ========================================
    # ADMINISTRACIÓN - BANCO DE PREGUNTAS
    # ========================================
    path('admin/preguntas/', listar_preguntas_view, name='listar_preguntas'),
    path('admin/preguntas/crear/', crear_pregunta_view, name='crear_pregunta'),
    path('admin/preguntas/<int:pregunta_id>/', detalle_pregunta_view, name='detalle_pregunta'),
    path('admin/preguntas/<int:pregunta_id>/actualizar/', actualizar_pregunta_view, name='actualizar_pregunta'),
    path('admin/preguntas/<int:pregunta_id>/eliminar/', eliminar_pregunta_view, name='eliminar_pregunta'),
    path('admin/preguntas/<int:pregunta_id>/editar-copia/', editar_copia_view, name='editar_copia_pregunta'),

    # ========================================
    # COMITÉ - ANALYTICS (Solo Lectura)
    # ========================================
    path('comite/cuestionarios/', listar_cuestionarios_comite_view, name='listar_cuestionarios_comite'),
    path('comite/cuestionarios/<int:cuestionario_id>/', detalle_cuestionario_comite_view, name='detalle_cuestionario_comite'),
    path('comite/cuestionarios/<int:cuestionario_id>/progreso/', progreso_cuestionario_comite_view, name='progreso_cuestionario_comite'),
    path('comite/cuestionarios/<int:cuestionario_id>/estadisticas/', estadisticas_cuestionario_comite_view, name='estadisticas_cuestionario_comite'),

    # COMITÉ - DASHBOARD
    path('comite/overview/', overview_comite_view, name='overview_comite'),
    path('comite/overview/progreso/', progreso_overview_comite_view, name='progreso_overview_comite'),
    path('comite/overview/alertas/', alertas_comite_view, name='alertas_comite'),
    path('comite/overview/centralidad/', centralidad_comite_view, name='centralidad_comite'),
    path('comite/graphs/', graphs_comite_view, name='graphs_comite'),
    
    # ========================================
    # ACADÉMICO (Tutores) - GRUPOS
    # ========================================
    path('academic/my-groups/', my_groups_view, name='my-groups'),
    
    # ========================================
    # ACADÉMICO (Tutores) - CUESTIONARIOS
    # ========================================
    path('academic/cuestionarios/', listar_cuestionarios_tutor_view, name='listar_cuestionarios_tutor'),
    path('academic/cuestionarios/<int:cuestionario_id>/', detalle_cuestionario_tutor_view, name='detalle_cuestionario_tutor'),
    path('academic/cuestionarios/<int:cuestionario_id>/progreso/', progreso_cuestionario_view, name='progreso_cuestionario'),
    path('academic/cuestionarios/<int:cuestionario_id>/estadisticas/', estadisticas_cuestionario_view, name='estadisticas_cuestionario'),
    path('academic/cuestionarios/<int:cuestionario_id>/registro/', registro_cuestionario_view, name='registro_cuestionario'),
    path('academic/cuestionarios/<int:cuestionario_id>/clasificacion-pregunta/', clasificacion_por_pregunta_view, name='clasificacion_por_pregunta'),

    # ========================================
    # ACADÉMICO (Tutores) - ARCHIVOS / EXPORTACIÓN
    # ========================================
    path('academic/archivos/cuestionarios/', listar_cuestionarios_historico_view, name='archivos_cuestionarios_historico'),
    path('academic/archivos/cuestionarios/<int:cuestionario_id>/sociograma/', datos_sociograma_view, name='datos_sociograma'),
    path('academic/archivos/cuestionarios/<int:cuestionario_id>/exportar/csv/', exportar_csv_view, name='exportar_csv'),
    path('academic/archivos/cuestionarios/<int:cuestionario_id>/exportar/pdf/', exportar_pdf_view, name='exportar_pdf'),

    # ========================================
    # ESTUDIANTES - CUESTIONARIOS
    # ========================================
    path('student/cuestionarios/disponibles/', cuestionarios_disponibles_view, name='cuestionarios_disponibles'),
    path('student/cuestionarios/<int:cuestionario_id>/', detalle_cuestionario_alumno_view, name='detalle_cuestionario_alumno'),
    path('student/cuestionarios/<int:cuestionario_id>/preguntas/', preguntas_cuestionario_view, name='preguntas_cuestionario'),
    path('student/cuestionarios/<int:cuestionario_id>/iniciar/', iniciar_cuestionario_view, name='iniciar_cuestionario'),
    path('student/cuestionarios/<int:cuestionario_id>/responder/', responder_cuestionario_view, name='responder_cuestionario'),
    path('student/cuestionarios/<int:cuestionario_id>/mi-progreso/', mi_progreso_view, name='mi_progreso'),

    path('', include(router.urls)),
]