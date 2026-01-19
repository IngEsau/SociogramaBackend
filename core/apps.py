from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Sistema Sociograma'
    
    def ready(self):
        """
        Código que se ejecuta cuando Django inicia.
        Útil para importar signals o registrar handlers.
        """
        pass