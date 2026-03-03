# core/views/admin/grupos.py
"""
Endpoints CRUD de Grupos (mínimo)
crear grupo individual / cambiar tutor del grupo
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import Grupo, Periodo, Programa, Docente, Auditoria
from core.utils.decorators import require_admin


def _get_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def crear_grupo_view(request):
    """
    Crea un grupo individual de forma manual.

    POST /api/admin/grupos/crear/
    Body:
    {
        "periodo_id": 1,
        "programa_id": 3,
        "grado": "3",
        "grupo": "A",
        "turno": "Matutino",
        "tutor_id": 5,          // opcional
        "cupo_maximo": 40       // opcional, default 40
    }

    Response:
    {
        "success": true,
        "grupo": {
            "id": 10,
            "clave": "ISC-3-A",
            "periodo": "2026-1",
            "programa": "ISC - Ingeniería en Sistemas",
            "grado": "3",
            "grupo": "A",
            "turno": "Matutino",
            "tutor": "Juan Pérez",
            "activo": true
        }
    }
    """
    periodo_id = request.data.get('periodo_id')
    programa_id = request.data.get('programa_id')
    grado = request.data.get('grado', '').strip()
    grupo_letra = request.data.get('grupo', '').strip()
    turno = request.data.get('turno', 'Matutino')
    tutor_id = request.data.get('tutor_id')
    cupo_maximo = request.data.get('cupo_maximo', 40)

    # Validaciones requeridas
    if not all([periodo_id, programa_id, grado, grupo_letra]):
        return Response(
            {'error': 'Se requieren: periodo_id, programa_id, grado, grupo'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if turno not in ['Matutino', 'Vespertino', 'Nocturno']:
        return Response(
            {'error': 'Turno debe ser: Matutino, Vespertino o Nocturno'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        periodo = Periodo.objects.get(id=periodo_id)
    except Periodo.DoesNotExist:
        return Response({'error': 'Periodo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    try:
        programa = Programa.objects.get(id=programa_id)
    except Programa.DoesNotExist:
        return Response({'error': 'Programa no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    tutor = None
    if tutor_id:
        try:
            tutor = Docente.objects.get(id=tutor_id)
        except Docente.DoesNotExist:
            return Response({'error': 'Docente no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    clave = f"{programa.codigo}-{grado}-{grupo_letra}"

    if Grupo.objects.filter(clave=clave, periodo=periodo).exists():
        return Response(
            {'error': f'Ya existe el grupo {clave} en el periodo {periodo.codigo}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    grupo = Grupo.objects.create(
        clave=clave,
        periodo=periodo,
        programa=programa,
        grado=grado,
        grupo=grupo_letra,
        turno=turno,
        tutor=tutor,
        cupo_maximo=cupo_maximo,
        activo=True,
    )

    Auditoria.objects.create(
        usuario=request.user,
        accion='CREAR_GRUPO',
        entidad='grupo',
        entidad_id=grupo.id,
        detalle={
            'clave': grupo.clave,
            'periodo': periodo.codigo,
            'programa': programa.codigo,
        },
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'grupo': {
            'id': grupo.id,
            'clave': grupo.clave,
            'periodo': periodo.codigo,
            'programa': str(programa),
            'grado': grupo.grado,
            'grupo': grupo.grupo,
            'turno': grupo.turno,
            'tutor': tutor.user.nombre_completo if tutor else None,
            'activo': grupo.activo,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@require_admin
def editar_tutor_grupo_view(request, grupo_id):
    """
    Cambia el tutor asignado a un grupo.
    Para quitar el tutor, enviar tutor_id: null.

    PATCH /api/admin/grupos/<grupo_id>/editar-tutor/
    Body:
    {
        "tutor_id": 5      // null para quitar el tutor
    }

    Response:
    {
        "success": true,
        "grupo": {
            "id": 10,
            "clave": "ISC-3-A",
            "tutor_anterior": "Carlos López",
            "tutor_nuevo": "Juan Pérez"
        }
    }
    """
    try:
        grupo = Grupo.objects.select_related('tutor__user', 'periodo').get(id=grupo_id)
    except Grupo.DoesNotExist:
        return Response({'error': 'Grupo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

    if 'tutor_id' not in request.data:
        return Response({'error': 'Se requiere el campo tutor_id'}, status=status.HTTP_400_BAD_REQUEST)

    tutor_id = request.data.get('tutor_id')
    tutor_anterior_nombre = grupo.tutor.user.nombre_completo if grupo.tutor else None

    if tutor_id is None:
        grupo.tutor = None
        tutor_nuevo_nombre = None
    else:
        try:
            tutor = Docente.objects.select_related('user').get(id=tutor_id)
        except Docente.DoesNotExist:
            return Response({'error': 'Docente no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        grupo.tutor = tutor
        tutor_nuevo_nombre = tutor.user.nombre_completo

    grupo.save(update_fields=['tutor'])

    Auditoria.objects.create(
        usuario=request.user,
        accion='EDITAR_GRUPO',
        entidad='grupo',
        entidad_id=grupo.id,
        detalle={
            'clave': grupo.clave,
            'tutor_anterior': tutor_anterior_nombre,
            'tutor_nuevo': tutor_nuevo_nombre,
        },
        ip_address=_get_ip(request),
    )

    return Response({
        'success': True,
        'grupo': {
            'id': grupo.id,
            'clave': grupo.clave,
            'tutor_anterior': tutor_anterior_nombre,
            'tutor_nuevo': tutor_nuevo_nombre,
        }
    }, status=status.HTTP_200_OK)
