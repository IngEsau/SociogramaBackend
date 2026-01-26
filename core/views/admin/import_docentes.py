# core/views/admin/import_docentes.py
"""
Endpoint para importación de docentes/tutores
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
import pandas as pd

from core.models import User, Division, Docente
from core.utils.decorators import require_admin
from .helpers import (
    limpiar_texto,
    generar_username,
    normalizar_genero,
)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
@parser_classes([MultiPartParser, FormParser])
def import_docentes_view(request):
    """
    Endpoint para importación masiva de DOCENTES/TUTORES
    
    POST /api/admin/import-docentes/
    
    Headers:
        Authorization: Bearer <access_token>
        Content-Type: multipart/form-data
    
    Body (form-data):
        file: archivo CSV con columnas:
            - No. Empleado (requerido)
            - Nombres (requerido)
            - A. Paterno
            - A. Materno
            - Sexo
            - Email
            - División
            - Es Tutor (SI/NO, YES/NO, 1/0)
            - Especialidad
            - Grado Académico
            - Puesto
    
    Permisos:
        - Solo usuarios ADMIN
    
    Response:
        {
            "success": true,
            "message": "Importación de docentes completada",
            "resumen": {
                "docentes_creados": 5,
                "docentes_actualizados": 2,
                "errores": []
            }
        }
    """
    
    # Verificar archivo
    if 'file' not in request.FILES:
        return Response(
            {'error': 'No se proporcionó ningún archivo. Use el campo "file" en form-data'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    archivo = request.FILES['file']
    
    # Validar extensión
    if not archivo.name.endswith('.csv'):
        return Response(
            {'error': f'El archivo debe ser CSV (.csv), recibido: {archivo.name}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Leer CSV
        df = pd.read_csv(archivo)
        
        # Validar columnas requeridas
        columnas_requeridas = ['No. Empleado', 'Nombres']
        
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            return Response(
                {
                    'error': f'Faltan las siguientes columnas: {", ".join(columnas_faltantes)}',
                    'columnas_encontradas': list(df.columns),
                    'columnas_requeridas': columnas_requeridas
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if df.empty:
            return Response(
                {'error': 'El archivo CSV está vacío'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Iniciar transacción
        with transaction.atomic():
            resumen = {
                'docentes_creados': 0,
                'docentes_actualizados': 0,
                'divisiones_creadas': 0,
            }
            errores = []
            
            # Cache de divisiones
            divisiones_cache = {}
            
            # Procesar fila por fila
            for idx, row in df.iterrows():
                try:
                    # Obtener datos básicos
                    numero_empleado = limpiar_texto(row.get('No. Empleado'))
                    nombres = limpiar_texto(row.get('Nombres'))
                    a_paterno = limpiar_texto(row.get('A. Paterno', ''))
                    a_materno = limpiar_texto(row.get('A. Materno', ''))
                    sexo = limpiar_texto(row.get('Sexo', ''))
                    email = limpiar_texto(row.get('Email', ''))
                    division_nombre = limpiar_texto(row.get('División', ''))
                    es_tutor_str = limpiar_texto(row.get('Es Tutor', 'NO'))
                    especialidad = limpiar_texto(row.get('Especialidad', ''))
                    grado_academico = limpiar_texto(row.get('Grado Académico', ''))
                    puesto = limpiar_texto(row.get('Puesto', ''))
                    
                    # Validar datos mínimos
                    if not numero_empleado or not nombres:
                        errores.append(f"Fila {idx+2}: Falta No. Empleado o Nombres")
                        continue
                    
                    # Procesar División
                    division = None
                    if division_nombre:
                        if division_nombre not in divisiones_cache:
                            import re
                            codigo_div = re.sub(r'[^A-Z]', '', division_nombre.upper())[:10] or division_nombre[:10].upper()
                            division, created = Division.objects.get_or_create(
                                codigo=codigo_div,
                                defaults={'nombre': division_nombre, 'activa': True}
                            )
                            divisiones_cache[division_nombre] = division
                            if created:
                                resumen['divisiones_creadas'] += 1
                        division = divisiones_cache[division_nombre]
                    
                    # Normalizar "Es Tutor"
                    es_tutor = False
                    if es_tutor_str:
                        es_tutor_lower = es_tutor_str.lower()
                        es_tutor = es_tutor_lower in ['si', 'sí', 'yes', 'y', '1', 'true']
                    
                    # Preparar datos del usuario
                    apellidos = f"{a_paterno or ''} {a_materno or ''}".strip()
                    nombre_completo = f"{nombres} {apellidos}".strip()
                    genero = normalizar_genero(sexo)
                    username = generar_username(numero_empleado)
                    
                    # Crear o actualizar User
                    user, user_created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'first_name': nombres,
                            'last_name': apellidos,
                            'email': email or f"{username}@utpuebla.edu.mx",
                            'is_staff': True,
                            'is_active': True,
                            'rol': 'DOCENTE',
                            'nombre_completo': nombre_completo,
                            'genero': genero,
                        }
                    )
                    
                    # Si es nuevo, establecer password
                    if user_created:
                        user.set_password(numero_empleado)
                        user.save()
                    else:
                        # Actualizar datos si ya existe
                        user.first_name = nombres
                        user.last_name = apellidos
                        user.nombre_completo = nombre_completo
                        if email:
                            user.email = email
                        if genero:
                            user.genero = genero
                        user.rol = 'DOCENTE'
                        user.is_staff = True
                        user.save()
                    
                    # Crear o actualizar Docente
                    docente, docente_created = Docente.objects.get_or_create(
                        profesor_id=numero_empleado,
                        defaults={
                            'user': user,
                            'division': division,
                            'es_tutor': es_tutor,
                            'especialidad': especialidad,
                            'grado_academico': grado_academico,
                            'estatus': 'ACTIVO'
                        }
                    )
                    
                    if docente_created:
                        resumen['docentes_creados'] += 1
                    else:
                        # Actualizar docente existente
                        docente.division = division
                        docente.es_tutor = es_tutor
                        if especialidad:
                            docente.especialidad = especialidad
                        if grado_academico:
                            docente.grado_academico = grado_academico
                        # Si viene puesto, actualizar especialidad con el puesto
                        if puesto and not especialidad:
                            docente.especialidad = puesto
                        docente.save()
                        resumen['docentes_actualizados'] += 1
                
                except Exception as e:
                    errores.append(f"Fila {idx+2}: {str(e)}")
            
            # Respuesta
            return Response({
                'success': True,
                'message': f'Importación de docentes completada{"" if not errores else " con algunos errores"}',
                'resumen': resumen,
                'errores': errores[:10] if errores else None,
                'estadisticas': {
                    'total_docentes': Docente.objects.count(),
                    'total_tutores': Docente.objects.filter(es_tutor=True).count(),
                }
            }, status=status.HTTP_200_OK)
        
    except pd.errors.EmptyDataError:
        return Response(
            {'error': 'El archivo CSV está vacío o corrupto'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Error al procesar el archivo CSV', 'detalle': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )