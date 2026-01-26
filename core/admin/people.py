# core/admin/people.py
"""
Administración de Personas del Sistema
Docente, Alumno
"""
from django.contrib import admin
from core.models import Docente, Alumno


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