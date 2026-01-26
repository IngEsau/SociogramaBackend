# core/views/admin/__init__.py
"""
Views de Administración
Importación masiva y funciones administrativas
"""
from .import_csv import import_csv_view

__all__ = [
    'import_csv_view',
]