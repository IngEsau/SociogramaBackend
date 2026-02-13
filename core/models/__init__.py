# core/models/__init__.py
"""
Módulo de modelos del Sistema Sociograma UTP
Importa y expone todos los modelos para uso en el proyecto
"""

# Modelo base
from .base import User

# Modelos académicos
from .academic import (
    Division,
    Programa,
    PlanEstudio,
    Periodo,
)

# Modelos de personas
from .people import (
    Docente,
    Alumno,
)

# Modelos de grupos
from .groups import (
    Grupo,
    AlumnoGrupo,
)

# Modelos de encuestas
from .surveys import (
    Pregunta,
    Opcion,
    Cuestionario,
    CuestionarioPregunta,
    CuestionarioEstado,
    Respuesta,
)

# Modelos de reportes
from .reports import (
    Reporte,
)

# Exportar todos los modelos
__all__ = [
    # Base
    'User',
    
    # Académicos
    'Division',
    'Programa',
    'PlanEstudio',
    'Periodo',
    
    # Personas
    'Docente',
    'Alumno',
    
    # Grupos
    'Grupo',
    'AlumnoGrupo',
    
    # Encuestas
    'Pregunta',
    'Opcion',
    'Cuestionario',
    'CuestionarioPregunta',
    'CuestionarioEstado',
    'Respuesta',
    
    # Reportes
    'Reporte',
]