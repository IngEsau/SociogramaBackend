# core/views/admin/__init__.py
"""
Views de Administración
Importación masiva y funciones administrativas
"""
from .import_csv import import_csv_view
from .import_docentes import import_docentes_view
from .import_alumnos import import_alumnos_view
from .asignar_tutor import asignar_tutor_view, remover_tutor_view
from .import_excel import analizar_importacion_view, ejecutar_importacion_view
from .periodos import (listar_periodos_view, activar_periodo_view, 
                       desactivar_periodo_view, crear_periodo_view,
                       obtener_periodo_activo_view)

__all__ = [
    'import_csv_view',
    'import_docentes_view',
    'import_alumnos_view',
    'asignar_tutor_view',
    'remover_tutor_view',
    'analizar_importacion_view',
    'ejecutar_importacion_view',
    'listar_periodos_view',
    'activar_periodo_view',
    'desactivar_periodo_view',
    'crear_periodo_view',
    'obtener_periodo_activo_view',
]