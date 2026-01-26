# core/admin/surveys.py
"""
Administración de Encuestas Sociométricas y Reportes
Pregunta, Opcion, Respuesta, Reporte
"""
from django.contrib import admin
from core.models import Pregunta, Opcion, Respuesta, Reporte


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