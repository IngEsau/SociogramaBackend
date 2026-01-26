# core/admin/__init__.py
"""
Configuración del Django Admin para el Sistema de Sociograma
Importa y registra todos los modelos de administración
"""
from django.contrib import admin

# Importar todas las clases admin para que se registren automáticamente
from .base import UserAdmin
from .academic import (
    DivisionAdmin,
    ProgramaAdmin,
    PlanEstudioAdmin,
    PeriodoAdmin,
)
from .people import (
    DocenteAdmin,
    AlumnoAdmin,
)
from .groups import (
    GrupoAdmin,
    AlumnoGrupoAdmin,
)
from .surveys import (
    PreguntaAdmin,
    OpcionAdmin,
    RespuestaAdmin,
    ReporteAdmin,
)

# Personalización del sitio de administración
admin.site.site_header = 'Administración Sociograma UTP'
admin.site.site_title = 'Sociograma UTP Admin'
admin.site.index_title = 'Panel de Administración'

# Exportar todas las clases admin
__all__ = [
    'UserAdmin',
    'DivisionAdmin',
    'ProgramaAdmin',
    'PlanEstudioAdmin',
    'PeriodoAdmin',
    'DocenteAdmin',
    'AlumnoAdmin',
    'GrupoAdmin',
    'AlumnoGrupoAdmin',
    'PreguntaAdmin',
    'OpcionAdmin',
    'RespuestaAdmin',
    'ReporteAdmin',
]