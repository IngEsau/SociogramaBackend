# core/admin/academic.py
"""
Administración de Catálogos Académicos
División, Programa, Plan de Estudio, Periodo
"""
from django.contrib import admin
from core.models import Division, Programa, PlanEstudio, Periodo


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