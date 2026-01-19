# Serializers de autenticación
from .auth import (
    UserSerializer,
    LoginSerializer,
    RegisterSerializer
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

# Serializers de docentes (NUEVO)
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
    
    # Catálogos
    'DivisionSerializer',
    'ProgramaSerializer',
    'PlanEstudioSerializer',
    'PeriodoSerializer',
    'ReporteSerializer',
]