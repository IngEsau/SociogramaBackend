# core/views/academic.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import Grupo, Periodo
from core.serializers.grupo import GrupoDetalleSerializer
from core.utils.decorators import require_tutor


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_tutor
def my_groups_view(request):
    """
    Listar grupos asignados al tutor autenticado
    
    GET /api/academic/my-groups/
    
    Permisos:
        - Solo usuarios con rol DOCENTE que sean tutores
        - Verificado por @require_tutor decorator
    
    Retorna:
        - Lista de grupos activos del periodo actual
        - Con información completa de alumnos inscritos
        - Ordenados por grado y grupo (1A, 1B, 2A, 2B...)
    
    Response:
        {
            "success": true,
            "total_grupos": 2,
            "periodo_actual": "2025-2",
            "grupos": [
                {
                    "id": 1,
                    "clave": "IDGS-5-A",
                    "grado": "5",
                    "grupo": "A",
                    "turno": "Matutino",
                    "programa_nombre": "Ingeniería en Desarrollo de Software",
                    "total_alumnos": 25,
                    "alumnos": [
                        {
                            "id": 1,
                            "matricula": "UTP001",
                            "nombre_completo": "Juan Pérez",
                            "email": "juan@alumno.utpuebla.edu.mx",
                            "semestre": 5,
                            "estatus": "ACTIVO",
                            "fecha_inscripcion": "2025-01-07"
                        }
                    ]
                }
            ]
        }
    """
    
    try:
        # Obtener el docente asociado al usuario autenticado
        docente = request.user.docente
        
        # Obtener periodo activo
        try:
            periodo_actual = Periodo.objects.get(activo=True)
        except Periodo.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'error': 'No hay un periodo activo configurado',
                    'grupos': []
                },
                status=status.HTTP_200_OK
            )
        
        # Obtener grupos del tutor en el periodo actual
        grupos = Grupo.objects.filter(
            tutor=docente,
            periodo=periodo_actual,
            activo=True
        ).select_related(
            'programa',
            'programa__division',
            'periodo',
            'tutor',
            'tutor__user'
        ).prefetch_related(
            'alumnos'
        ).order_by('grado', 'grupo')
        
        # Serializar
        serializer = GrupoDetalleSerializer(grupos, many=True)
        
        return Response({
            'success': True,
            'total_grupos': grupos.count(),
            'periodo_actual': periodo_actual.codigo,
            'periodo_nombre': periodo_actual.nombre,
            'grupos': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {
                'success': False,
                'error': 'Error al obtener los grupos',
                'detalle': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )