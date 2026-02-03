# core/utils/validators.py
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re


def validate_matricula(value):
    """
    Valida que la matrícula tenga el formato correcto.
    Ejemplo: 2022030001 (4 dígitos año + 2 dígitos programa + 4 dígitos consecutivo)
    """
    if not re.match(r'^\d{10}$', value):
        raise ValidationError(
            _('La matrícula debe tener 10 dígitos numéricos'),
            code='invalid_matricula'
        )
    
    # Validar que el año sea razonable (entre 2000 y 2099)
    anio = int(value[:4])
    if anio < 2000 or anio > 2099:
        raise ValidationError(
            _('El año en la matrícula no es válido'),
            code='invalid_year'
        )


def validate_nss(value):
    """
    Valida que el NSS tenga un formato válido.
    NSS en México: 11 dígitos
    """
    if not re.match(r'^\d{11}$', value):
        raise ValidationError(
            _('El NSS debe tener 11 dígitos numéricos'),
            code='invalid_nss'
        )


def validate_phone_number(value):
    """
    Valida que el teléfono tenga un formato válido.
    Acepta: 10 dígitos (México)
    """
    # Remover espacios, guiones, paréntesis
    cleaned = re.sub(r'[\s\-\(\)]', '', value)
    
    if not re.match(r'^\d{10}$', cleaned):
        raise ValidationError(
            _('El teléfono debe tener 10 dígitos'),
            code='invalid_phone'
        )


def validate_positive(value):
    """
    Valida que un número sea positivo
    """
    if value <= 0:
        raise ValidationError(
            _('Este valor debe ser positivo'),
            code='not_positive'
        )


def validate_promedio(value):
    """
    Valida que el promedio esté entre 0 y 10
    """
    if value < 0 or value > 10:
        raise ValidationError(
            _('El promedio debe estar entre 0 y 10'),
            code='invalid_average'
        )


def validate_semestre(value):
    """
    Valida que el semestre sea válido (1-12)
    """
    if value < 1 or value > 12:
        raise ValidationError(
            _('El semestre debe estar entre 1 y 12'),
            code='invalid_semester'
        )


def validate_file_size(value):
    """
    Valida que un archivo no exceda 5MB
    """
    filesize = value.size
    
    if filesize > 5 * 1024 * 1024:  # 5MB
        raise ValidationError(
            _('El archivo no debe exceder 5MB'),
            code='file_too_large'
        )


def validate_image_extension(value):
    """
    Valida que el archivo sea una imagen válida
    """
    import os
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    
    if ext not in valid_extensions:
        raise ValidationError(
            _('Solo se permiten imágenes (JPG, PNG, GIF, WEBP)'),
            code='invalid_image'
        )


def validate_no_self_selection(alumno, seleccionado):
    """
    Valida que un alumno no se seleccione a sí mismo
    """
    if alumno == seleccionado:
        raise ValidationError(
            _('No puedes seleccionarte a ti mismo'),
            code='self_selection'
        )


def validate_max_selections(pregunta, num_selecciones):
    """
    Valida que no se excedan las selecciones máximas permitidas
    """
    if num_selecciones > pregunta.max_elecciones:
        raise ValidationError(
            _(f'No puedes seleccionar más de {pregunta.max_elecciones} opciones'),
            code='too_many_selections'
        )