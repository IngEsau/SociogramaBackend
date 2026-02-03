# core/views/importacion.py
"""
Endpoints para importación masiva de datos desde Excel
"""
import os
import re
import tempfile
import uuid
from datetime import datetime
from rest_framework import status
from django.db import transaction
from collections import defaultdict
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.cache import cache
import pandas as pd

from core.utils.decorators import require_admin
from core.models import (
    User, Division, Programa, PlanEstudio, Periodo, 
    Docente, Grupo, Alumno, AlumnoGrupo
)
from core.utils.import_excel_helpers import (
    validar_estructura_excel,
    leer_hoja_excel,
    generar_preview_datos,
    obtener_periodos_disponibles,
    sugerir_periodo,
    limpiar_texto,
    generar_username,
    normalizar_genero,
    crear_periodo,
    calcular_estadisticas_cambios,
)
from core.serializers.import_excel import (
    AnalisisImportacionSerializer,
    EjecucionImportacionSerializer
)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
@parser_classes([MultiPartParser, FormParser])
def analizar_importacion_view(request):
    """
    PASO 1: Analiza el archivo Excel y retorna opciones para la importación
    
    POST /api/admin/importacion/analizar/
    Content-Type: multipart/form-data
    Body:
        - archivo: datos.xlsx
    
    Response:
    {
        "archivo_valido": true,
        "archivo_id": "temp_abc123",
        "hojas_encontradas": {...},
        "preview": {...},
        "periodos_disponibles": [...],
        "periodo_sugerido": {...}
    }
    """
    serializer = AnalisisImportacionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Archivo requerido', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    archivo = serializer.validated_data['archivo']
    
    # Validar extensión
    if not archivo.name.endswith(('.xlsx', '.xls')):
        return Response(
            {'error': 'El archivo debe ser un Excel (.xlsx o .xls)'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    excel_file = None

    try:
        # Guardar archivo temporalmente
        archivo_id = f"temp_{uuid.uuid4().hex[:12]}"
        temp_path = os.path.join(tempfile.gettempdir(), f"{archivo_id}.xlsx")
        
        with open(temp_path, 'wb+') as destination:
            for chunk in archivo.chunks():
                destination.write(chunk)
        
        # Leer Excel
        excel_file = pd.ExcelFile(temp_path)
        
        # Validar estructura
        valido, errores, hojas_map = validar_estructura_excel(excel_file)
        
        if not valido:
            excel_file.close()
            # Limpiar archivo temporal
            os.remove(temp_path)
            return Response(
                {
                    'archivo_valido': False,
                    'errores': errores
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Leer hojas
        df_alumnos = leer_hoja_excel(excel_file, hojas_map['alumnos'])
        df_grupos = leer_hoja_excel(excel_file, hojas_map['grupos'])
        df_tutores = leer_hoja_excel(excel_file, hojas_map['tutores'])
        df_inscritos = leer_hoja_excel(excel_file, hojas_map['inscritos'])

        # CERRAR después de leer
        excel_file.close()
        excel_file = None
        
        # Generar preview
        preview = generar_preview_datos(df_alumnos, df_grupos, df_tutores, df_inscritos)
        
        # Obtener periodos disponibles
        periodos_disponibles = obtener_periodos_disponibles()
        periodo_sugerido = sugerir_periodo(periodos_disponibles)
        
        # Guardar ruta del archivo en cache (expira en 1 hora)
        cache.set(f"importacion_{archivo_id}", temp_path, 3600)
        
        return Response({
            'archivo_valido': True,
            'archivo_id': archivo_id,
            'hojas_encontradas': {
                'alumnos': hojas_map['alumnos'] is not None,
                'grupos': hojas_map['grupos'] is not None,
                'tutores': hojas_map['tutores'] is not None,
                'inscritos': hojas_map['inscritos'] is not None,
            },
            'preview': preview,
            'periodos_disponibles': periodos_disponibles,
            'periodo_sugerido': periodo_sugerido,
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        # Limpiar archivo temporal si existe
        if excel_file is not None:
            try:
                excel_file.close()
            except:
                pass
        
        # Limpiar archivo temporal
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except PermissionError:
            pass
        
        return Response(
            {
                'error': 'Error al procesar el archivo',
                'detail': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_admin
def ejecutar_importacion_view(request):
    """
    PASO 2: Ejecuta la importación con las opciones seleccionadas
    
    POST /api/admin/importacion/ejecutar/
    Body:
    {
        "archivo_id": "temp_abc123",
        "periodo_id": 1,
        "crear_periodo": false,
        "nuevo_periodo_anio": 2026,
        "nuevo_periodo_numero": 1,
        "desactivar_anteriores": true
    }
    
    Response:
    {
        "success": true,
        "periodo": {...},
        "resultados": {...},
        "cambios_alumnado": {...},
        "errores": [...],
        "log": "..."
    }
    """
    serializer = EjecucionImportacionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Datos inválidos', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    data = serializer.validated_data
    archivo_id = data['archivo_id']
    
    # Recuperar archivo temporal del cache
    temp_path = cache.get(f"importacion_{archivo_id}")
    
    if not temp_path or not os.path.exists(temp_path):
        return Response(
            {'error': 'Archivo no encontrado o expirado. Por favor sube el archivo nuevamente.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    excel_file = None

    try:
        # Leer Excel
        excel_file = pd.ExcelFile(temp_path)
        
        # Detectar hojas
        hojas_map = {}
        for nombre_hoja in excel_file.sheet_names:
            nombre_lower = nombre_hoja.lower()
            if 'alumnos' in nombre_lower:
                hojas_map['alumnos'] = nombre_hoja
            elif 'grupos' in nombre_lower:
                hojas_map['grupos'] = nombre_hoja
            elif 'tutores' in nombre_lower:
                hojas_map['tutores'] = nombre_hoja
            elif 'inscritos' in nombre_lower or 'relaci' in nombre_lower:
                hojas_map['inscritos'] = nombre_hoja
        
        # Leer hojas
        df_alumnos = leer_hoja_excel(excel_file, hojas_map['alumnos'])
        df_grupos = leer_hoja_excel(excel_file, hojas_map['grupos'])
        df_tutores = leer_hoja_excel(excel_file, hojas_map['tutores'])
        df_inscritos = leer_hoja_excel(excel_file, hojas_map['inscritos'])
        
        excel_file.close()
        excel_file = None
        
        # Obtener o crear periodo
        if data.get('crear_periodo'):
            periodo = crear_periodo(
                data['nuevo_periodo_anio'],
                data['nuevo_periodo_numero']
            )
        else:
            periodo = Periodo.objects.get(id=data['periodo_id'])
        
        # Inicializar contadores
        resultados = {
            'periodos_desactivados': 0,
            'grupos_desactivados': 0,
            'inscripciones_desactivadas': 0,
            'divisiones_creadas': 0,
            'programas_creados': 0,
            'tutores_creados': 0,
            'grupos_creados': 0,
            'alumnos_creados': 0,
            'relaciones_creadas': 0,
        }
        
        errores = []
        log_messages = []
        
        # =====================================================================
        # INICIAR TRANSACCIÓN
        # =====================================================================
        with transaction.atomic():
            
            # 1. DESACTIVAR PERIODOS ANTERIORES
            if data.get('desactivar_anteriores'):
                log_messages.append("Desactivando periodos anteriores...")
                
                resultados['periodos_desactivados'] = Periodo.objects.exclude(
                    id=periodo.id
                ).filter(activo=1).update(activo=0)
                
                resultados['grupos_desactivados'] = Grupo.objects.filter(
                    periodo__activo=0, 
                    activo=1
                ).update(activo=0)
                
                resultados['inscripciones_desactivadas'] = AlumnoGrupo.objects.filter(
                    grupo__periodo__activo=0,
                    activo=1
                ).update(activo=0)
                
                # Activar periodo actual
                Periodo.objects.filter(id=periodo.id).update(activo=1)
                
                log_messages.append(
                    f"✓ Desactivados: {resultados['periodos_desactivados']} periodos, "
                    f"{resultados['grupos_desactivados']} grupos, "
                    f"{resultados['inscripciones_desactivadas']} inscripciones"
                )
            
            # 2. IMPORTAR DIVISIONES Y PROGRAMAS
            log_messages.append("Importando divisiones y programas...")
            divisiones_cache, programas_cache, stats = importar_divisiones_programas(
                df_alumnos, df_grupos
            )
            resultados['divisiones_creadas'] = stats['divisiones']
            resultados['programas_creados'] = stats['programas']
            log_messages.append(f"✓ Divisiones: {stats['divisiones']}, Programas: {stats['programas']}")
            
            # 3. IMPORTAR TUTORES
            log_messages.append("Importando tutores...")
            tutores_cache, tutores_stats = importar_tutores(df_tutores, divisiones_cache)
            resultados['tutores_creados'] = tutores_stats['creados']
            if tutores_stats['errores']:
                errores.extend(tutores_stats['errores'])
            log_messages.append(f"✓ Tutores creados: {tutores_stats['creados']}")
            
            # 4. IMPORTAR GRUPOS
            log_messages.append("Importando grupos...")
            grupos_cache, grupos_stats = importar_grupos(
                df_grupos, programas_cache, tutores_cache, periodo
            )
            resultados['grupos_creados'] = grupos_stats['creados']
            if grupos_stats['errores']:
                errores.extend(grupos_stats['errores'])
            log_messages.append(f"✓ Grupos creados: {grupos_stats['creados']}")
            
            # 5. IMPORTAR ALUMNOS
            log_messages.append("Importando alumnos...")
            alumnos_cache, alumnos_stats = importar_alumnos(df_alumnos, programas_cache)
            resultados['alumnos_creados'] = alumnos_stats['creados']
            if alumnos_stats['errores']:
                errores.extend(alumnos_stats['errores'])
            log_messages.append(f"✓ Alumnos creados: {alumnos_stats['creados']}")
            
            # 6. IMPORTAR RELACIONES
            log_messages.append("Creando inscripciones...")
            relaciones_stats = importar_relaciones_inscritos(
                df_inscritos, alumnos_cache, grupos_cache
            )
            resultados['relaciones_creadas'] = relaciones_stats['creados']
            if relaciones_stats['errores']:
                errores.extend(relaciones_stats['errores'])
            log_messages.append(f"✓ Inscripciones creadas: {relaciones_stats['creados']}")
        
        # 7. CALCULAR ESTADÍSTICAS DE CAMBIOS
        log_messages.append("Calculando estadísticas...")
        cambios_alumnado = calcular_estadisticas_cambios(periodo)
        
        # Limpiar archivo temporal
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except PermissionError:
            # Si aún así falla, solo logear pero no fallar la importación
            pass
        
        cache.delete(f"importacion_{archivo_id}")
        
        log_messages.append("✓ Importación completada exitosamente")
        
        return Response({
            'success': True,
            'periodo': {
                'id': periodo.id,
                'codigo': periodo.codigo,
                'nombre': periodo.nombre,
                'activo': periodo.activo == 1,
            },
            'resultados': resultados,
            'cambios_alumnado': cambios_alumnado,
            'errores': errores[:50] if errores else [],  # Máximo 50 errores
            'total_errores': len(errores),
            'log': '\n'.join(log_messages),
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        if excel_file is not None:
            try:
                excel_file.close()
            except:
                pass
        
        # Limpiar archivo temporal
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        except PermissionError:
            # Si no se puede borrar, solo ignorar
            pass
        
        cache.delete(f"importacion_{archivo_id}")
        
        return Response(
            {
                'success': False,
                'error': 'Error durante la importación',
                'detail': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# FUNCIONES DE IMPORTACIÓN
# =============================================================================

def importar_divisiones_programas(df_alumnos, df_grupos):
    """
    Importa divisiones y programas
    
    Returns:
        tuple: (divisiones_cache, programas_cache, stats)
    """
    divisiones_cache = {}
    programas_cache = {}
    stats = {'divisiones': 0, 'programas': 0}
    
    # Obtener divisiones únicas
    divisiones_unicas = set()
    if 'División' in df_alumnos.columns:
        divisiones_unicas.update(df_alumnos['División'].dropna().unique())
    if 'División' in df_grupos.columns:
        divisiones_unicas.update(df_grupos['División'].dropna().unique())
    
    # Crear divisiones
    for div_nombre in divisiones_unicas:
        div_nombre = limpiar_texto(div_nombre)
        if not div_nombre:
            continue
            
        codigo = re.sub(r'[^A-Z]', '', div_nombre.upper())[:10]
        if not codigo:
            codigo = div_nombre[:10].upper()
        
        division, created = Division.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': div_nombre,
                'activa': 1
            }
        )
        
        divisiones_cache[div_nombre] = division
        if created:
            stats['divisiones'] += 1
    
    # Obtener programas únicos
    programas_unicos = set()
    if 'Programa' in df_alumnos.columns:
        programas_unicos.update(df_alumnos['Programa'].dropna().unique())
    if 'Programa' in df_grupos.columns:
        programas_unicos.update(df_grupos['Programa'].dropna().unique())
    
    # Crear programas
    for prog_nombre in programas_unicos:
        prog_nombre = limpiar_texto(prog_nombre)
        if not prog_nombre:
            continue
        
        # Buscar división correspondiente
        division = None
        for div_nombre, div_obj in divisiones_cache.items():
            mask_alumnos = (df_alumnos['Programa'] == prog_nombre) if 'Programa' in df_alumnos.columns else pd.Series([False] * len(df_alumnos))
            if mask_alumnos.any():
                div_alumno = df_alumnos.loc[mask_alumnos, 'División'].iloc[0]
                if limpiar_texto(div_alumno) == div_nombre:
                    division = div_obj
                    break
        
        if not division and divisiones_cache:
            division = list(divisiones_cache.values())[0]
        
        # Generar código
        nombre_limpio = re.sub(r'\s*-\s*\d{4}', '', prog_nombre)
        palabras = nombre_limpio.split()
        
        if len(palabras) >= 3:
            codigo = ''.join([p[0].upper() for p in palabras if len(p) > 2])[:8]
        elif len(palabras) == 2:
            codigo = ''.join([p[:4].upper() for p in palabras])[:8]
        else:
            codigo = ''.join([c.upper() for c in nombre_limpio if c.isalnum()])[:8]
        
        if not codigo or len(codigo) < 2:
            codigo = nombre_limpio.replace(' ', '')[:20].upper()
        
        programa, created = Programa.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': prog_nombre,
                'division': division,
                'duracion_semestres': 9,
                'activo': 1
            }
        )
        
        programas_cache[prog_nombre] = programa
        if created:
            stats['programas'] += 1
    
    return divisiones_cache, programas_cache, stats


def importar_tutores(df_tutores, divisiones_cache):
    """
    Importa tutores usando bulk_create (OPTIMIZADO)
    
    Returns:
        tuple: (tutores_cache, stats)
    """
    from datetime import date
    
    tutores_cache = {}
    stats = {'creados': 0, 'errores': []}
    
    # Obtener IDs existentes de una sola vez
    empleados_existentes = set(
        Docente.objects.values_list('profesor_id', flat=True)
    )
    
    usernames_existentes = set(
        User.objects.filter(rol='DOCENTE').values_list('username', flat=True)
    )
    
    # Listas para bulk create
    users_to_create = []
    docentes_to_create = []
    
    # Primera pasada: preparar users para crear
    for idx, row in df_tutores.iterrows():
        try:
            empleado_id = limpiar_texto(row.get('No. de empleado'))
            nombres = limpiar_texto(row.get('Nombres', ''))
            a_paterno = limpiar_texto(row.get('A. Paterno', ''))
            a_materno = limpiar_texto(row.get('A. Materno', ''))
            sexo = limpiar_texto(row.get('Sexo', ''))
            email = limpiar_texto(row.get('Email', ''))
            
            if not empleado_id or not nombres:
                continue
            
            # Si el docente ya existe, recuperarlo
            if empleado_id in empleados_existentes:
                docente = Docente.objects.select_related('user').get(profesor_id=empleado_id)
                tutores_cache[empleado_id] = docente
                continue
            
            apellidos = f"{a_paterno or ''} {a_materno or ''}".strip()
            nombre_completo = f"{nombres} {apellidos}".strip()
            genero = normalizar_genero(sexo)
            username = generar_username(empleado_id)
            
            # Si el user no existe, prepararlo para bulk create
            if username not in usernames_existentes:
                user = User(
                    username=username,
                    first_name=nombres,
                    last_name=apellidos,
                    email=email or f"{username}@utpuebla.edu.mx",
                    is_staff=True,
                    is_active=True,
                    rol='DOCENTE',
                    nombre_completo=nombre_completo,
                    genero=genero,
                )
                user.set_password(empleado_id)
                users_to_create.append(user)
                usernames_existentes.add(username)
                
        except Exception as e:
            stats['errores'].append(f"Tutor fila {idx+2}: {str(e)}")
    
    # Bulk create users
    if users_to_create:
        User.objects.bulk_create(users_to_create, batch_size=100, ignore_conflicts=True)
        stats['creados'] = len(users_to_create)
    
    # Segunda pasada: crear docentes
    if users_to_create:
        # Obtener users recién creados
        usernames_nuevos = [u.username for u in users_to_create]
        users_dict = {
            u.username: u 
            for u in User.objects.filter(username__in=usernames_nuevos)
        }
        
        for idx, row in df_tutores.iterrows():
            try:
                empleado_id = limpiar_texto(row.get('No. de empleado'))
                if not empleado_id or empleado_id in empleados_existentes:
                    continue
                
                username = generar_username(empleado_id)
                if username not in users_dict:
                    continue
                
                division_nombre = limpiar_texto(row.get('División', ''))
                puesto = limpiar_texto(row.get('Puesto', ''))
                division = divisiones_cache.get(division_nombre)
                
                docente = Docente(
                    profesor_id=empleado_id,
                    user=users_dict[username],
                    division=division,
                    es_tutor=True,
                    especialidad=puesto,
                    estatus='ACTIVO'
                )
                docentes_to_create.append(docente)
                
            except Exception as e:
                continue
        
        # Bulk create docentes
        if docentes_to_create:
            Docente.objects.bulk_create(docentes_to_create, batch_size=100, ignore_conflicts=True)
        
        # Actualizar cache con los nuevos
        for docente in docentes_to_create:
            tutores_cache[docente.profesor_id] = docente
    
    # Cargar docentes existentes al cache
    for docente in Docente.objects.filter(profesor_id__in=empleados_existentes).select_related('user'):
        tutores_cache[docente.profesor_id] = docente
    
    return tutores_cache, stats


def importar_grupos(df_grupos, programas_cache, tutores_cache, periodo):
    """
    Importa grupos
    """
    grupos_cache = {}
    stats = {'creados': 0, 'errores': []}
    
    for idx, row in df_grupos.iterrows():
        try:
            cuatrimestre_str = limpiar_texto(row.get('Cuatrimestre'))
            grupo_clave = limpiar_texto(row.get('Grupo'))
            programa_nombre = limpiar_texto(row.get('Programa'))
            tutor_nombre = limpiar_texto(row.get('Tutor Asignado', ''))
            turno = limpiar_texto(row.get('Turno', 'Matutino'))
            
            if not grupo_clave or not programa_nombre:
                continue
            
            if turno and turno.lower() not in ['matutino', 'vespertino', 'nocturno']:
                turno = 'Matutino'
            elif turno:
                turno = turno.capitalize()
            
            programa = programas_cache.get(programa_nombre)
            if not programa:
                stats['errores'].append(f"Grupo fila {idx+2}: Programa no encontrado '{programa_nombre}'")
                continue
            
            # Buscar tutor
            tutor = None
            if tutor_nombre:
                for empleado_id, doc in tutores_cache.items():
                    # ⭐ FIX: Verificar que el docente tiene ID (fue guardado)
                    if not hasattr(doc, 'id') or doc.id is None:
                        continue
                    
                    nombre_completo = doc.user.nombre_completo or doc.user.get_full_name()
                    if tutor_nombre.lower() in nombre_completo.lower():
                        tutor = doc
                        break
            
            # Extraer grado
            grado_match = re.match(r'^\d+', str(cuatrimestre_str)) 
            grado_final = grado_match.group(0) if grado_match else 'SG'
            
            clave_unica_bd = f"{programa.codigo}-{grado_final}-{grupo_clave}"
            
            grupo, created = Grupo.objects.get_or_create(
                clave=clave_unica_bd,
                periodo=periodo,
                defaults={
                    'grado': grado_final, 
                    'grupo': grupo_clave,
                    'turno': turno or 'Matutino',
                    'programa': programa,
                    'tutor': tutor,  # ← Ahora solo asigna si tiene ID
                    'activo': 1,
                    'cupo_maximo': 40
                }
            )
            
            cache_key = (programa_nombre, cuatrimestre_str, grupo_clave)
            grupos_cache[cache_key] = grupo
            
            if created:
                stats['creados'] += 1
                
        except Exception as e:
            stats['errores'].append(f"Grupo fila {idx+2}: {str(e)}")
    
    return grupos_cache, stats


def importar_alumnos(df_alumnos, programas_cache):
    """
    Importa alumnos usando bulk_create (OPTIMIZADO)
    
    Returns:
        tuple: (alumnos_cache, stats)
    """
    from datetime import date
    
    alumnos_cache = {}
    stats = {'creados': 0, 'errores': []}
    
    # Obtener matrículas existentes de una sola vez
    matriculas_existentes = set(
        Alumno.objects.values_list('matricula', flat=True)
    )
    
    usernames_existentes = set(
        User.objects.filter(rol='ALUMNO').values_list('username', flat=True)
    )
    
    # Listas para bulk create
    users_to_create = []
    alumnos_to_create = []
    planes_cache = {}
    
    # Crear planes de estudio necesarios
    for prog_nombre, programa in programas_cache.items():
        plan_codigo = f"{programa.codigo}-2020"
        if plan_codigo not in planes_cache:
            plan, _ = PlanEstudio.objects.get_or_create(
                codigo=plan_codigo,
                programa=programa,
                defaults={
                    'nombre': plan_codigo,
                    'anio_inicio': 2020,
                    'activo': 1
                }
            )
            planes_cache[plan_codigo] = plan
    
    # Primera pasada: preparar users para crear
    for idx, row in df_alumnos.iterrows():
        try:
            matricula = limpiar_texto(row.get('Matrícula'))
            nombres = limpiar_texto(row.get('Nombres', ''))
            a_paterno = limpiar_texto(row.get('A. Paterno', ''))
            a_materno = limpiar_texto(row.get('A. Materno', ''))
            sexo = limpiar_texto(row.get('Sexo', ''))
            email = limpiar_texto(row.get('Email Institucional') or row.get('Email', ''))
            
            if not matricula or not nombres:
                continue
            
            # Si el alumno ya existe, recuperarlo
            if matricula in matriculas_existentes:
                alumno = Alumno.objects.select_related('user').get(matricula=matricula)
                alumnos_cache[matricula] = alumno
                continue
            
            apellidos = f"{a_paterno or ''} {a_materno or ''}".strip()
            nombre_completo = f"{nombres} {apellidos}".strip()
            genero = normalizar_genero(sexo)
            username = generar_username(matricula)
            
            # Si el user no existe, prepararlo para bulk create
            if username not in usernames_existentes:
                user = User(
                    username=username,
                    first_name=nombres,
                    last_name=apellidos,
                    email=email or f"{username}@alumno.utpuebla.edu.mx",
                    is_active=True,
                    rol='ALUMNO',
                    nombre_completo=nombre_completo,
                    genero=genero,
                )
                user.set_password(matricula)
                users_to_create.append(user)
                usernames_existentes.add(username)
                
        except Exception as e:
            stats['errores'].append(f"Alumno fila {idx+2}: {str(e)}")
    
    # Bulk create users
    if users_to_create:
        User.objects.bulk_create(users_to_create, batch_size=500, ignore_conflicts=True)
        stats['creados'] = len(users_to_create)
    
    # Segunda pasada: crear alumnos
    if users_to_create:
        # Obtener users recién creados
        usernames_nuevos = [u.username for u in users_to_create]
        users_dict = {
            u.username: u 
            for u in User.objects.filter(username__in=usernames_nuevos)
        }
        
        for idx, row in df_alumnos.iterrows():
            try:
                matricula = limpiar_texto(row.get('Matrícula'))
                if not matricula or matricula in matriculas_existentes:
                    continue
                
                username = generar_username(matricula)
                if username not in users_dict:
                    continue
                
                nss = limpiar_texto(row.get('NSS', ''))
                programa_nombre = limpiar_texto(row.get('Programa', ''))
                programa = programas_cache.get(programa_nombre)
                
                plan_estudio = None
                if programa:
                    plan_codigo = f"{programa.codigo}-2020"
                    plan_estudio = planes_cache.get(plan_codigo)
                
                alumno = Alumno(
                    matricula=matricula,
                    user=users_dict[username],
                    nss=nss,
                    plan_estudio=plan_estudio,
                    semestre_actual=1,
                    estatus='ACTIVO'
                )
                alumnos_to_create.append(alumno)
                
            except Exception as e:
                continue
        
        # Bulk create alumnos
        if alumnos_to_create:
            Alumno.objects.bulk_create(alumnos_to_create, batch_size=500, ignore_conflicts=True)
        
        # Actualizar cache con los nuevos
        matriculas_nuevas = [a.matricula for a in alumnos_to_create]
        for alumno in Alumno.objects.filter(matricula__in=matriculas_nuevas).select_related('user'):
            alumnos_cache[alumno.matricula] = alumno
    
    # Cargar alumnos existentes al cache
    for alumno in Alumno.objects.filter(matricula__in=matriculas_existentes).select_related('user'):
        alumnos_cache[alumno.matricula] = alumno
    
    return alumnos_cache, stats


def importar_relaciones_inscritos(df_inscritos, alumnos_cache, grupos_cache):
    """
    Importa relaciones alumno-grupo usando bulk_create (OPTIMIZADO)
    
    Returns:
        dict: stats
    """
    from datetime import date
    
    stats = {'creados': 0, 'errores': []}
    
    # Obtener IDs de alumnos y grupos del cache
    alumnos_ids = [a.id for a in alumnos_cache.values() if hasattr(a, 'id')]
    grupos_ids = [g.id for g in grupos_cache.values() if hasattr(g, 'id')]
    
    # Obtener relaciones existentes de una sola vez
    relaciones_existentes = set(
        AlumnoGrupo.objects.filter(
            alumno_id__in=alumnos_ids,
            grupo_id__in=grupos_ids
        ).values_list('alumno_id', 'grupo_id')
    )
    
    # Lista para bulk create
    relaciones_to_create = []
    
    for idx, row in df_inscritos.iterrows():
        try:
            matricula = limpiar_texto(row.get('Matrícula'))
            grupo_clave = limpiar_texto(row.get('Grupo'))
            programa_nombre = limpiar_texto(row.get('Programa'))
            cuatrimestre_str = limpiar_texto(row.get('Cuatrimestre'))
            
            cache_key = (programa_nombre, cuatrimestre_str, grupo_clave)
            
            if not matricula or not all(cache_key):
                continue
            
            alumno = alumnos_cache.get(matricula)
            grupo = grupos_cache.get(cache_key)
            
            if not alumno or not grupo:
                continue
            
            # Verificar si la relación ya existe
            if (alumno.id, grupo.id) in relaciones_existentes:
                continue
            
            relacion = AlumnoGrupo(
                alumno=alumno,
                grupo=grupo,
                fecha_inscripcion=date.today(),
                activo=1
            )
            relaciones_to_create.append(relacion)
            stats['creados'] += 1
            
        except Exception as e:
            stats['errores'].append(f"Relación fila {idx+2}: {str(e)}")
    
    # Bulk create relaciones
    if relaciones_to_create:
        AlumnoGrupo.objects.bulk_create(
            relaciones_to_create, 
            batch_size=1000, 
            ignore_conflicts=True
        )
    
    return stats