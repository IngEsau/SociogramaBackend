# core/views/student/__init__.py
"""
Views de Student (Alumnos)
"""

from .cuestionarios import (
    cuestionarios_disponibles_view,
    detalle_cuestionario_alumno_view,
    preguntas_cuestionario_view,
    responder_cuestionario_view,
    mi_progreso_view,
)

__all__ = [
    'cuestionarios_disponibles_view',
    'detalle_cuestionario_alumno_view',
    'preguntas_cuestionario_view',
    'responder_cuestionario_view',
    'mi_progreso_view',
]