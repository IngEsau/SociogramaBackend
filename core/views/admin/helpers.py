# core/views/admin/helpers.py
"""
Funciones auxiliares para importación de datos CSV
Extraídas de views/admin.py para mejor organización
"""
import pandas as pd
import re
from datetime import date
from core.models import Periodo


def limpiar_texto(texto):
    """Limpiar y validar texto de CSV"""
    if pd.isna(texto) or texto == '':
        return None
    return str(texto).strip()


def generar_username(matricula_o_empleado):
    """Generar username a partir de matrícula o número de empleado"""
    return str(matricula_o_empleado).strip().lower().replace(' ', '')


def normalizar_genero(sexo):
    """
    Normalizar campo de género desde diferentes formatos
    H/M/Masculino/Femenino -> Masculino/Femenino/Otro
    """
    if not sexo:
        return None
    sexo_lower = str(sexo).lower()
    if 'h' in sexo_lower or 'm' == sexo_lower or 'masc' in sexo_lower:
        return 'Masculino'
    elif 'f' in sexo_lower or 'mujer' in sexo_lower or 'fem' in sexo_lower:
        return 'Femenino'
    return 'Otro'


def crear_o_obtener_periodo():
    """
    Crear u obtener el periodo académico actual
    """
    periodo, created = Periodo.objects.get_or_create(
        codigo='2025-2',
        defaults={
            'nombre': 'Mayo - Agosto 2025',
            'fecha_inicio': date(2025, 5, 1),
            'fecha_fin': date(2025, 8, 31),
            'activo': True
        }
    )
    return periodo