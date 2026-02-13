# core/views/academic/__init__.py
"""
Views de Academic (Tutores)
"""

# Vista existente de grupos
from .academic import my_groups_view

# Vistas de cuestionarios
from .cuestionarios import (
    listar_cuestionarios_tutor_view,
    detalle_cuestionario_tutor_view,
    progreso_cuestionario_view,
    estadisticas_cuestionario_view,
)

__all__ = [
    # Grupos
    'my_groups_view',
    
    # Cuestionarios
    'listar_cuestionarios_tutor_view',
    'detalle_cuestionario_tutor_view',
    'progreso_cuestionario_view',
    'estadisticas_cuestionario_view',
]