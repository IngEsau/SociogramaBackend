# core/utils/email.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_password_reset_email(user_email, reset_token, user_name=None):
    """
    Envía correo de recuperación de contraseña
    
    Args:
        user_email (str): Email del destinatario
        reset_token (str): Token JWT para reset
        user_name (str, optional): Nombre del usuario
    
    Returns:
        bool: True si se envió exitosamente, False en caso contrario
    """
    try:
        # URL del frontend donde el usuario ingresará la nueva contraseña
        frontend_url = settings.FRONTEND_URL
        reset_link = f"{frontend_url}/reset-password?token={reset_token}"
        
        # Contexto para el template
        context = {
            'user_name': user_name or 'Usuario',
            'reset_link': reset_link,
            'valid_hours': 1,  # Token válido por 1 hora
        }
        
        # Renderizar template HTML
        html_message = render_to_string('emails/password_reset.html', context)
        
        # Mensaje de texto plano (fallback)
        plain_message = f"""
        Hola {context['user_name']},
        
        Recibimos una solicitud para restablecer tu contraseña en Sociograma UTP.
        
        Para restablecer tu contraseña, haz clic en el siguiente enlace:
        {reset_link}
        
        Este enlace es válido por {context['valid_hours']} hora.
        
        Si no solicitaste este cambio, puedes ignorar este correo.
        
        Saludos,
        Equipo Sociograma UTP
        """
        
        # Enviar correo
        send_mail(
            subject='Recuperación de Contraseña - Sociograma UTP',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        #logger.info(f"Correo de recuperación enviado a {user_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error al enviar correo a {user_email}: {str(e)}")
        return False