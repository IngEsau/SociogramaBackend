# core/admin/base.py
"""
Administración del modelo User extendido
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from core.models import User


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