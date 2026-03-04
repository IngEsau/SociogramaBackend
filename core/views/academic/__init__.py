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
    registro_cuestionario_view,
    clasificacion_por_pregunta_view,
)

# Vistas de exportación (CSV, PDF, datos sociograma histórico)
from .archivos import (
    listar_cuestionarios_historico_view,
    datos_sociograma_view,
    exportar_csv_view,
    exportar_pdf_view,
)

__all__ = [
    # Grupos
    'my_groups_view',

    # Cuestionarios
    'listar_cuestionarios_tutor_view',
    'detalle_cuestionario_tutor_view',
    'progreso_cuestionario_view',
    'estadisticas_cuestionario_view',
    'registro_cuestionario_view',
    'clasificacion_por_pregunta_view',

    # Archivos / Exportación
    'listar_cuestionarios_historico_view',
    'datos_sociograma_view',
    'exportar_csv_view',
    'exportar_pdf_view',
]