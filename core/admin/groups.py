# core/admin/groups.py
"""
Administración de Grupos y Relaciones
Grupo, AlumnoGrupo
"""
from django.contrib import admin
from core.models import Grupo, AlumnoGrupo


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