"""
Configuración del Django Admin para el Sistema de Sociograma
CORREGIDO - Con User extendido
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Division, Programa, PlanEstudio, Periodo, Docente, Grupo, Alumno, 
    AlumnoGrupo, Pregunta, Opcion, Respuesta, Reporte
)


# ==================== USER ADMIN EXTENDIDO ====================

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin personalizado para User extendido"""
    
    # Campos a mostrar en la lista
    list_display = ['username', 'email', 'nombre_completo', 'rol', 'is_staff', 'is_active']
    list_filter = ['rol', 'is_staff', 'is_active', 'genero']
    search_fields = ['username', 'first_name', 'last_name', 'email', 'nombre_completo']
    
    # Organización de campos en el formulario
    fieldsets = (
        ('Información de Acceso', {
            'fields': ('username', 'password')
        }),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'nombre_completo', 'email', 'telefono', 'fecha_nacimiento', 'genero')
        }),
        ('Permisos y Rol', {
            'fields': ('rol', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Fechas Importantes', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    # Campos para crear nuevo usuario
    add_fieldsets = (
        ('Información de Acceso', {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'nombre_completo', 'email', 'genero')
        }),
        ('Rol y Permisos', {
            'fields': ('rol', 'is_staff', 'is_active')
        }),
    )
    
    # Filtros rápidos
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('docente', 'alumno')


# ==================== DIVISION ====================

@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'activa']
    list_filter = ['activa']
    search_fields = ['nombre', 'codigo', 'descripcion']
    
    fieldsets = (
        ('Información Principal', {
            'fields': ('codigo', 'nombre', 'descripcion', 'activa')
        }),
    )


# ==================== PROGRAMA ====================

@admin.register(Programa)
class ProgramaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'division', 'duracion_semestres', 'activo']
    list_filter = ['division', 'activo']
    search_fields = ['nombre', 'codigo']
    
    fieldsets = (
        ('Información Principal', {
            'fields': ('codigo', 'nombre', 'division', 'duracion_semestres', 'activo')
        }),
    )


# ==================== PLAN ESTUDIO ====================

@admin.register(PlanEstudio)
class PlanEstudioAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'programa', 'anio_inicio', 'activo']
    list_filter = ['programa', 'activo', 'anio_inicio']
    search_fields = ['codigo', 'nombre']
    
    fieldsets = (
        ('Información del Plan', {
            'fields': ('codigo', 'nombre', 'programa', 'anio_inicio', 'activo')
        }),
    )


# ==================== PERIODO ====================

@admin.register(Periodo)
class PeriodoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'fecha_inicio', 'fecha_fin', 'activo']
    list_filter = ['activo', 'fecha_inicio']
    search_fields = ['codigo', 'nombre']
    date_hierarchy = 'fecha_inicio'
    
    fieldsets = (
        ('Información del Periodo', {
            'fields': ('codigo', 'nombre', 'fecha_inicio', 'fecha_fin', 'activo')
        }),
    )


# ==================== DOCENTE ====================

@admin.register(Docente)
class DocenteAdmin(admin.ModelAdmin):
    list_display = ['profesor_id', 'get_nombre', 'division', 'es_tutor', 'estatus']
    list_filter = ['division', 'es_tutor', 'estatus']
    search_fields = ['profesor_id', 'user__first_name', 'user__last_name', 'user__email', 'user__nombre_completo']
    
    fieldsets = (
        ('Información del Docente', {
            'fields': ('profesor_id', 'user', 'division')
        }),
        ('Detalles Académicos', {
            'fields': ('especialidad', 'grado_academico', 'fecha_ingreso')
        }),
        ('Configuración', {
            'fields': ('es_tutor', 'estatus')
        }),
    )
    
    def get_nombre(self, obj):
        return obj.user.nombre_completo or obj.user.get_full_name() or obj.user.username
    get_nombre.short_description = 'Nombre'
    get_nombre.admin_order_field = 'user__nombre_completo'


# ==================== GRUPO ====================

@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ['clave', 'grado', 'grupo', 'programa', 'periodo', 'tutor', 'turno', 'activo']
    list_filter = ['programa', 'periodo', 'turno', 'activo']
    search_fields = ['clave', 'tutor__profesor_id', 'tutor__user__nombre_completo']
    
    fieldsets = (
        ('Información del Grupo', {
            'fields': ('clave', 'grado', 'grupo', 'turno')
        }),
        ('Asignaciones', {
            'fields': ('programa', 'periodo', 'tutor')
        }),
        ('Configuración', {
            'fields': ('cupo_maximo', 'activo')
        }),
    )


# ==================== ALUMNO ====================

@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ['matricula', 'get_nombre', 'plan_estudio', 'semestre_actual', 'promedio', 'estatus']
    list_filter = ['plan_estudio', 'semestre_actual', 'estatus']
    search_fields = ['matricula', 'nss', 'user__first_name', 'user__last_name', 'user__email', 'user__nombre_completo']
    
    fieldsets = (
        ('Información del Alumno', {
            'fields': ('matricula', 'user', 'nss')
        }),
        ('Información Académica', {
            'fields': ('plan_estudio', 'semestre_actual', 'promedio', 'fecha_ingreso')
        }),
        ('Estado', {
            'fields': ('estatus',)
        }),
    )
    
    def get_nombre(self, obj):
        return obj.user.nombre_completo or obj.user.get_full_name() or obj.user.username
    get_nombre.short_description = 'Nombre'
    get_nombre.admin_order_field = 'user__nombre_completo'


# ==================== ALUMNO-GRUPO ====================

@admin.register(AlumnoGrupo)
class AlumnoGrupoAdmin(admin.ModelAdmin):
    list_display = ['alumno', 'grupo', 'fecha_inscripcion', 'activo', 'fecha_baja']
    list_filter = ['grupo', 'activo', 'fecha_inscripcion']
    search_fields = ['alumno__matricula', 'grupo__clave']
    date_hierarchy = 'fecha_inscripcion'
    
    fieldsets = (
        ('Relación Alumno-Grupo', {
            'fields': ('alumno', 'grupo', 'activo')
        }),
        ('Fechas', {
            'fields': ('fecha_inscripcion', 'fecha_baja', 'motivo_baja')
        }),
    )


# ==================== PREGUNTA Y OPCIONES ====================

class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 1
    fields = ['orden', 'texto', 'valor']


@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ['orden', 'tipo', 'texto_corto', 'activa']
    list_filter = ['tipo', 'activa']
    search_fields = ['texto']
    inlines = [OpcionInline]
    
    fieldsets = (
        ('Configuración de la Pregunta', {
            'fields': ('orden', 'tipo', 'activa')
        }),
        ('Contenido', {
            'fields': ('texto', 'descripcion', 'max_elecciones')
        }),
    )
    
    def texto_corto(self, obj):
        return obj.texto[:60] + '...' if len(obj.texto) > 60 else obj.texto
    texto_corto.short_description = 'Texto'


@admin.register(Opcion)
class OpcionAdmin(admin.ModelAdmin):
    list_display = ['pregunta', 'orden', 'texto', 'valor']
    list_filter = ['pregunta']
    search_fields = ['texto', 'pregunta__texto']


# ==================== RESPUESTA ====================

@admin.register(Respuesta)
class RespuestaAdmin(admin.ModelAdmin):
    list_display = ['alumno', 'pregunta', 'seleccionado_alumno', 'orden_eleccion', 'puntaje', 'creado_en']
    list_filter = ['pregunta', 'creado_en']
    search_fields = ['alumno__matricula', 'seleccionado_alumno__matricula', 'texto_respuesta']
    readonly_fields = ['creado_en', 'modificado_en']
    date_hierarchy = 'creado_en'
    
    fieldsets = (
        ('Información de la Respuesta', {
            'fields': ('alumno', 'pregunta')
        }),
        ('Respuesta', {
            'fields': ('opcion', 'texto_respuesta', 'seleccionado_alumno', 'orden_eleccion', 'puntaje')
        }),
        ('Metadatos', {
            'fields': ('creado_en', 'modificado_en'),
            'classes': ('collapse',)
        }),
    )


# ==================== REPORTE ====================

@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'grupo', 'titulo', 'generado_por', 'creado_en']
    list_filter = ['tipo', 'creado_en']
    search_fields = ['titulo', 'descripcion', 'grupo__clave']
    readonly_fields = ['creado_en', 'actualizado_en']
    date_hierarchy = 'creado_en'
    
    fieldsets = (
        ('Información del Reporte', {
            'fields': ('tipo', 'grupo', 'titulo', 'descripcion')
        }),
        ('Datos', {
            'fields': ('data_json', 'archivo_path'),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('generado_por', 'creado_en', 'actualizado_en'),
            'classes': ('collapse',)
        }),
    )


# ==================== PERSONALIZACIÓN DEL SITIO ====================

admin.site.site_header = 'Administración Sociograma UTP'
admin.site.site_title = 'Sociograma UTP Admin'
admin.site.index_title = 'Panel de Administración'