# core/views/comite/__init__.py
"""
Views de Comité
Acceso de solo lectura a analytics y sociogramas de todos los grupos
El rol COMITÉ puede:
- Ver cuestionarios de cualquier periodo
- Ver progreso de cualquier grupo
- Ver sociogramas de cualquier grupo
- Filtrar por division, programa, grupo, periodo, cuestionario

El rol COMITÉ NO puede:
- Crear, editar o eliminar nada
- Acceder a endpoints de /admin/
- Importar datos
"""

from .cuestionarios import (
    listar_cuestionarios_comite_view,
    detalle_cuestionario_comite_view,
    progreso_cuestionario_comite_view,
    estadisticas_cuestionario_comite_view,
)

__all__ = [
    'listar_cuestionarios_comite_view',
    'detalle_cuestionario_comite_view',
    'progreso_cuestionario_comite_view',
    'estadisticas_cuestionario_comite_view',
]