# core/utils/importacion_helpers.py
"""
Funciones auxiliares para importación de datos desde Excel
"""
import re
import pandas as pd
from datetime import date
from core.models import (
    Division, Programa, PlanEstudio, Periodo, 
    Docente, Grupo, Alumno, AlumnoGrupo, User
)


def limpiar_texto(texto):
    """Limpia y normaliza texto de Excel"""
    if pd.isna(texto) or texto == '':
        return None
    return str(texto).strip()


def generar_username(matricula_o_empleado):
    """Genera username a partir de matrícula o número de empleado"""
    return str(matricula_o_empleado).strip().lower().replace(' ', '')


def normalizar_genero(sexo):
    """
    Normaliza el género desde Excel
    Acepta: H, M, Hombre, Mujer, Masculino, Femenino, etc.
    """
    if not sexo:
        return None
    
    sexo_lower = str(sexo).lower().strip()
    
    if 'h' in sexo_lower or 'm' == sexo_lower or 'masculino' in sexo_lower:
        return 'Masculino'
    elif 'f' in sexo_lower or 'mujer' in sexo_lower or 'femenino' in sexo_lower:
        return 'Femenino'
    
    return None


def validar_estructura_excel(excel_file):
    """
    Valida que el archivo Excel tenga la estructura correcta
    
    Returns:
        tuple: (valido: bool, errores: list, hojas_map: dict)
    """
    errores = []
    hojas_map = {
        'alumnos': None,
        'grupos': None,
        'tutores': None,
        'inscritos': None
    }
    
    try:
        # Leer nombres de hojas
        hojas_disponibles = excel_file.sheet_names
        
        # Mapear hojas
        for nombre_hoja in hojas_disponibles:
            nombre_lower = nombre_hoja.lower()
            if 'alumnos' in nombre_lower:
                hojas_map['alumnos'] = nombre_hoja
            elif 'grupos' in nombre_lower:
                hojas_map['grupos'] = nombre_hoja
            elif 'tutores' in nombre_lower:
                hojas_map['tutores'] = nombre_hoja
            elif 'inscritos' in nombre_lower or 'relaci' in nombre_lower:
                hojas_map['inscritos'] = nombre_hoja
        
        # Validar que existan las hojas necesarias
        hojas_faltantes = [k for k, v in hojas_map.items() if v is None]
        if hojas_faltantes:
            errores.append(f"Faltan las siguientes hojas: {', '.join(hojas_faltantes)}")
        
        valido = len(errores) == 0
        return valido, errores, hojas_map
        
    except Exception as e:
        errores.append(f"Error al leer Excel: {str(e)}")
        return False, errores, hojas_map


def detectar_header_row(excel_file, nombre_hoja, max_rows=10):
    """
    Detecta automáticamente la fila donde comienza el header
    
    Returns:
        int: Número de fila (0-indexed)
    """
    for i in range(max_rows):
        try:
            df_test = pd.read_excel(excel_file, sheet_name=nombre_hoja, header=i, nrows=1)
            cols_str = ' '.join(str(col).lower() for col in df_test.columns)
            
            # Buscar palabras clave según el tipo de hoja
            if 'matricula' in cols_str or 'matrícula' in cols_str:
                return i
            elif 'empleado' in cols_str or 'nombres' in cols_str:
                return i
            elif 'grupo' in cols_str or 'cuatrimestre' in cols_str:
                return i
        except:
            continue
    
    return 0  # Default


def leer_hoja_excel(excel_file, nombre_hoja):
    """
    Lee una hoja de Excel con detección inteligente de header
    
    Returns:
        pd.DataFrame
    """
    if not nombre_hoja:
        return pd.DataFrame()
    
    header_row = detectar_header_row(excel_file, nombre_hoja)
    df = pd.read_excel(excel_file, sheet_name=nombre_hoja, header=header_row)
    
    return df


def generar_preview_datos(df_alumnos, df_grupos, df_tutores, df_inscritos):
    """
    Genera un preview de los datos a importar
    
    Returns:
        dict: Estadísticas de los datos
    """
    return {
        'total_alumnos': len(df_alumnos),
        'total_grupos': len(df_grupos),
        'total_tutores': len(df_tutores),
        'total_relaciones': len(df_inscritos),
        'programas_unicos': df_alumnos['Programa'].nunique() if 'Programa' in df_alumnos.columns else 0,
        'divisiones_unicas': df_alumnos['División'].nunique() if 'División' in df_alumnos.columns else 0,
    }


def obtener_periodos_disponibles():
    """
    Obtiene lista de periodos disponibles con información adicional
    
    Returns:
        list: Lista de periodos con sus datos
    """
    periodos = Periodo.objects.all().order_by('-codigo')
    
    periodos_data = []
    for periodo in periodos:
        grupos_count = Grupo.objects.filter(periodo=periodo, activo=1).count()
        alumnos_count = AlumnoGrupo.objects.filter(
            grupo__periodo=periodo, 
            activo=1
        ).count()
        
        periodos_data.append({
            'id': periodo.id,
            'codigo': periodo.codigo,
            'nombre': periodo.nombre,
            'activo': periodo.activo == 1,
            'fecha_inicio': periodo.fecha_inicio.isoformat() if periodo.fecha_inicio else None,
            'fecha_fin': periodo.fecha_fin.isoformat() if periodo.fecha_fin else None,
            'grupos_actuales': grupos_count,
            'alumnos_actuales': alumnos_count,
        })
    
    return periodos_data


def sugerir_periodo(periodos_data):
    """
    Sugiere el periodo más apropiado para la importación
    
    Returns:
        dict: Periodo sugerido con razón
    """
    if not periodos_data:
        return None
    
    # Buscar periodo más reciente sin datos
    for periodo in periodos_data:
        if periodo['grupos_actuales'] == 0:
            return {
                'id': periodo['id'],
                'codigo': periodo['codigo'],
                'razon': 'Periodo más reciente sin datos'
            }
    
    # Si todos tienen datos, sugerir el activo
    periodo_activo = next((p for p in periodos_data if p['activo']), None)
    if periodo_activo:
        return {
            'id': periodo_activo['id'],
            'codigo': periodo_activo['codigo'],
            'razon': 'Periodo actualmente marcado como activo'
        }
    
    # Si no hay activo, sugerir el más reciente
    return {
        'id': periodos_data[0]['id'],
        'codigo': periodos_data[0]['codigo'],
        'razon': 'Periodo más reciente'
    }


def generar_codigo_periodo(anio, numero):
    """Genera código de periodo según convención UTP"""
    return f"{anio}-{numero}"


def generar_nombre_periodo(anio, numero):
    """Genera nombre de periodo según convención UTP"""
    nombres = {
        1: f"Enero - Abril {anio}",
        2: f"Mayo - Agosto {anio}",
        3: f"Septiembre - Diciembre {anio}"
    }
    return nombres.get(numero, f"Periodo {anio}-{numero}")


def generar_fechas_periodo(anio, numero):
    """
    Genera fechas de inicio y fin según el periodo
    
    Returns:
        tuple: (fecha_inicio, fecha_fin)
    """
    fechas = {
        1: ((1, 15), (4, 30)),
        2: ((5, 1), (8, 31)),
        3: ((9, 1), (12, 15))
    }
    
    inicio, fin = fechas.get(numero, ((1, 1), (12, 31)))
    fecha_inicio = date(anio, inicio[0], inicio[1])
    fecha_fin = date(anio, fin[0], fin[1])
    
    return fecha_inicio, fecha_fin


def crear_periodo(anio, numero):
    """
    Crea un nuevo periodo
    
    Returns:
        Periodo: Objeto periodo creado
    """
    codigo = generar_codigo_periodo(anio, numero)
    nombre = generar_nombre_periodo(anio, numero)
    fecha_inicio, fecha_fin = generar_fechas_periodo(anio, numero)
    
    periodo, created = Periodo.objects.get_or_create(
        codigo=codigo,
        defaults={
            'nombre': nombre,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'activo': 1
        }
    )
    
    return periodo


def calcular_estadisticas_cambios(periodo_actual):
    """
    Calcula estadísticas de alumnos nuevos, continuos y bajas
    
    Returns:
        dict: Estadísticas de cambios
    """
    # Alumnos del periodo actual
    alumnos_actuales = set(
        AlumnoGrupo.objects.filter(
            grupo__periodo=periodo_actual,
            activo=1
        ).values_list('alumno__matricula', flat=True)
    )
    
    # Buscar periodo anterior
    periodo_anterior = Periodo.objects.filter(
        activo=0
    ).order_by('-codigo').first()
    
    if not periodo_anterior:
        return {
            'nuevos': len(alumnos_actuales),
            'continuos': 0,
            'bajas': 0,
            'periodo_anterior': None
        }
    
    # Alumnos del periodo anterior
    alumnos_anteriores = set(
        AlumnoGrupo.objects.filter(
            grupo__periodo=periodo_anterior,
            activo=0
        ).values_list('alumno__matricula', flat=True)
    )
    
    # Calcular diferencias
    nuevos = alumnos_actuales - alumnos_anteriores
    continuos = alumnos_actuales & alumnos_anteriores
    bajas = alumnos_anteriores - alumnos_actuales
    
    return {
        'nuevos': len(nuevos),
        'continuos': len(continuos),
        'bajas': len(bajas),
        'periodo_anterior': periodo_anterior.codigo,
        'lista_bajas': list(bajas) if len(bajas) <= 100 else list(bajas)[:100]
    }