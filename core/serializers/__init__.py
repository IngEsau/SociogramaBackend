# core/serializers/__init__.py
"""
Exportación centralizada de serializers
"""

# Serializers de autenticación
from .auth import (
    UserSerializer,
    LoginSerializer,
    RegisterSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)

# Serializers de modelos principales
from .alumno import (
    AlumnoSerializer,
    AlumnoSimpleSerializer,
    AlumnoGrupoSerializer
)

from .grupo import (
    GrupoSerializer
)

from .pregunta import (
    PreguntaSerializer,
    OpcionSerializer,
    RespuestaSerializer,
    RespuestaCreateSerializer
)

# Serializers de cuestionarios
from .cuestionario import (
    CuestionarioListSerializer,
    CuestionarioDetailSerializer,
    CuestionarioCreateSerializer,
    CuestionarioUpdateSerializer,
    CuestionarioPreguntaSerializer,
    CuestionarioEstadoSerializer,
    AgregarPreguntaSerializer,
    ProgresoAlumnoSerializer,
)

# Serializers de docentes
from .docente import (
    DocenteSerializer,
    DocenteSimpleSerializer
)

# Serializers de catálogos
from .catalogos import (
    DivisionSerializer,
    ProgramaSerializer,
    PlanEstudioSerializer,
    PeriodoSerializer,
    ReporteSerializer
)

__all__ = [
    # Auth
    'UserSerializer',
    'LoginSerializer',
    'RegisterSerializer',
    'PasswordResetRequestSerializer',
    'PasswordResetConfirmSerializer',
    
    # Alumno
    'AlumnoSerializer',
    'AlumnoSimpleSerializer',
    'AlumnoGrupoSerializer',
    
    # Grupo
    'GrupoSerializer',
    
    # Docente
    'DocenteSerializer',
    'DocenteSimpleSerializer',
    
    # Pregunta/Respuesta
    'PreguntaSerializer',
    'OpcionSerializer',
    'RespuestaSerializer',
    'RespuestaCreateSerializer',
    
    # Cuestionarios
    'CuestionarioListSerializer',
    'CuestionarioDetailSerializer',
    'CuestionarioCreateSerializer',
    'CuestionarioUpdateSerializer',
    'CuestionarioPreguntaSerializer',
    'CuestionarioEstadoSerializer',
    'AgregarPreguntaSerializer',
    'ProgresoAlumnoSerializer',
    
    # Catálogos
    'DivisionSerializer',
    'ProgramaSerializer',
    'PlanEstudioSerializer',
    'PeriodoSerializer',
    'ReporteSerializer',
]