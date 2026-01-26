# core/views/admin/asignar_tutor.py
"""
Endpoint para asignar o cambiar tutor de un grupo
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import Grupo, Docente
from core.utils.decorators import require_admin


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def asignar_tutor_view(request):
    """
    Endpoint para asignar o cambiar el tutor de un grupo
    
    POST /api/admin/asignar-tutor/
    
    Headers:
        Authorization: Bearer <access_token>
        Content-Type: application/json
    
    Body:
        {
            "grupo_id": 5,  // o "clave_grupo": "ISC-1-A"
            "tutor_empleado": "T001"  // Número de empleado del docente
        }
    
    Permisos:
        - Solo usuarios ADMIN
    
    Response:
        {
            "success": true,
            "message": "Tutor asignado correctamente",
            "grupo": {
                "id": 5,
                "clave": "ISC-1-A",
                "tutor": "T001 - María González"
            }
        }
    """
    
    # Obtener datos del request
    grupo_id = request.data.get('grupo_id')
    clave_grupo = request.data.get('clave_grupo')
    tutor_empleado = request.data.get('tutor_empleado')
    
    # Validar que se proporcionó identificador del grupo
    if not grupo_id and not clave_grupo:
        return Response(
            {'error': 'Debe proporcionar grupo_id o clave_grupo'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validar que se proporcionó tutor
    if not tutor_empleado:
        return Response(
            {'error': 'Debe proporcionar tutor_empleado'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Buscar grupo
        if grupo_id:
            grupo = Grupo.objects.get(id=grupo_id)
        else:
            grupo = Grupo.objects.get(clave=clave_grupo, activo=True)
        
        # Buscar docente
        try:
            docente = Docente.objects.get(profesor_id=tutor_empleado, estatus='ACTIVO')
        except Docente.DoesNotExist:
            return Response(
                {'error': f'Docente con No. Empleado {tutor_empleado} no existe o no está activo'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar que el docente sea tutor
        if not docente.es_tutor:
            # Actualizar para que sea tutor
            docente.es_tutor = True
            docente.save()
        
        # Asignar tutor al grupo
        tutor_anterior = grupo.tutor
        grupo.tutor = docente
        grupo.save()
        
        # Preparar respuesta
        response_data = {
            'success': True,
            'message': 'Tutor asignado correctamente',
            'grupo': {
                'id': grupo.id,
                'clave': grupo.clave,
                'grado': grupo.grado,
                'grupo': grupo.grupo,
                'programa': grupo.programa.nombre,
                'periodo': grupo.periodo.nombre,
                'tutor': {
                    'empleado': docente.profesor_id,
                    'nombre': docente.user.nombre_completo or docente.user.get_full_name(),
                    'email': docente.user.email,
                }
            }
        }
        
        # Si había tutor anterior, incluirlo en la respuesta
        if tutor_anterior:
            response_data['tutor_anterior'] = {
                'empleado': tutor_anterior.profesor_id,
                'nombre': tutor_anterior.user.nombre_completo or tutor_anterior.user.get_full_name(),
            }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except Grupo.DoesNotExist:
        return Response(
            {'error': f'Grupo no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Grupo.MultipleObjectsReturned:
        return Response(
            {'error': f'Múltiples grupos encontrados con clave {clave_grupo}. Use grupo_id en su lugar'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Error al asignar tutor', 'detalle': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def remover_tutor_view(request):
    """
    Endpoint para remover el tutor de un grupo
    
    POST /api/admin/remover-tutor/
    
    Body:
        {
            "grupo_id": 5  // o "clave_grupo": "ISC-1-A"
        }
    """
    
    grupo_id = request.data.get('grupo_id')
    clave_grupo = request.data.get('clave_grupo')
    
    if not grupo_id and not clave_grupo:
        return Response(
            {'error': 'Debe proporcionar grupo_id o clave_grupo'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Buscar grupo
        if grupo_id:
            grupo = Grupo.objects.get(id=grupo_id)
        else:
            grupo = Grupo.objects.get(clave=clave_grupo, activo=True)
        
        # Guardar info del tutor anterior
        tutor_anterior = None
        if grupo.tutor:
            tutor_anterior = {
                'empleado': grupo.tutor.profesor_id,
                'nombre': grupo.tutor.user.nombre_completo or grupo.tutor.user.get_full_name(),
            }
        
        # Remover tutor
        grupo.tutor = None
        grupo.save()
        
        return Response({
            'success': True,
            'message': 'Tutor removido correctamente',
            'grupo': {
                'id': grupo.id,
                'clave': grupo.clave,
            },
            'tutor_removido': tutor_anterior
        }, status=status.HTTP_200_OK)
    
    except Grupo.DoesNotExist:
        return Response(
            {'error': 'Grupo no encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': 'Error al remover tutor', 'detalle': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )