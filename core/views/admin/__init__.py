# core/views/admin/__init__.py
"""
Views de Administración
Importación masiva y funciones administrativas
"""

# ========================================
# IMPORTACIONES DE DATOS
# ========================================
from .import_csv import import_csv_view
from .import_docentes import import_docentes_view
from .import_alumnos import import_alumnos_view
from .import_excel import analizar_importacion_view, ejecutar_importacion_view

# ========================================
# GESTIÓN DE TUTORES
# ========================================
from .asignar_tutor import asignar_tutor_view, remover_tutor_view

# ========================================
# GESTIÓN DE PERIODOS
# ========================================
from .periodos import (
    listar_periodos_view, 
    activar_periodo_view, 
    desactivar_periodo_view, 
    crear_periodo_view,
    obtener_periodo_activo_view
)

# ========================================
# GESTIÓN DE CUESTIONARIOS
# ========================================
from .cuestionarios import (
    crear_cuestionario_view,
    listar_cuestionarios_view,
    detalle_cuestionario_view,
    actualizar_cuestionario_view,
    eliminar_cuestionario_view,
    activar_cuestionario_view,
    desactivar_cuestionario_view,
    agregar_pregunta_view,
    remover_pregunta_view,
    asociar_pregunta_view,
)

from .preguntas import (
    listar_preguntas_view, 
    crear_pregunta_view, 
    detalle_pregunta_view, 
    actualizar_pregunta_view, 
    eliminar_pregunta_view,
    editar_copia_view,
)


__all__ = [
    # Importaciones
    'import_csv_view',
    'import_docentes_view',
    'import_alumnos_view',
    'analizar_importacion_view',
    'ejecutar_importacion_view',
    
    # Tutores
    'asignar_tutor_view',
    'remover_tutor_view',
    
    # Periodos
    'listar_periodos_view',
    'activar_periodo_view',
    'desactivar_periodo_view',
    'crear_periodo_view',
    'obtener_periodo_activo_view',
    
    # Cuestionarios
    'crear_cuestionario_view',
    'listar_cuestionarios_view',
    'detalle_cuestionario_view',
    'actualizar_cuestionario_view',
    'eliminar_cuestionario_view',
    'activar_cuestionario_view',
    'desactivar_cuestionario_view',
    'agregar_pregunta_view',
    'remover_pregunta_view',
    'asociar_pregunta_view',

    # Preguntas
    'listar_preguntas_view',
    'crear_pregunta_view',
    'detalle_pregunta_view',
    'actualizar_pregunta_view',
    'eliminar_pregunta_view',
    'editar_copia_view',
]