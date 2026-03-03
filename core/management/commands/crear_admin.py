# core/management/commands/crear_admin.py
import getpass

from django.core.management.base import BaseCommand, CommandError

from core.models import User


class Command(BaseCommand):
    help = 'Crea o actualiza el usuario administrador del sistema.'

    def add_arguments(self, parser):
        parser.add_argument('--username',   help='Username del admin')
        parser.add_argument('--first-name', help='Nombre(s)')
        parser.add_argument('--last-name',  help='Apellidos')
        parser.add_argument('--email',      help='Correo electrónico')
        parser.add_argument('--password',   help='Contraseña (si no se pasa, se pide interactivamente)')
        parser.add_argument('--actualizar', action='store_true',
                            help='Si el usuario ya existe, actualizar sus datos')

    def _prompt(self, label, default=None, secret=False):
        """Pide un valor por consola. Si secret=True oculta la entrada."""
        display = f'{label} [{default}]: ' if default else f'{label}: '
        if secret:
            value = getpass.getpass(display)
        else:
            value = input(display).strip()
        return value or default or ''

    def handle(self, *args, **options):
        username   = options['username']   or self._prompt('Username')
        first_name = options['first_name'] or self._prompt('Nombre(s)')
        last_name  = options['last_name']  or self._prompt('Apellidos')
        email      = options['email']      or self._prompt('Email')
        password   = options['password']
        actualizar = options['actualizar']

        if not username:
            raise CommandError('El username es obligatorio.')

        # Pedir password interactivamente si no se pasó como argumento
        if not password:
            password = self._prompt('Contraseña', secret=True)
            confirm  = self._prompt('Confirmar contraseña', secret=True)
            if password != confirm:
                raise CommandError('Las contraseñas no coinciden.')

        if not password:
            raise CommandError('La contraseña no puede estar vacía.')

        user_exists = User.objects.filter(username=username).exists()

        if user_exists:
            if not actualizar:
                raise CommandError(
                    f"El usuario '{username}' ya existe. "
                    f"Usa --actualizar para sobreescribir sus datos."
                )
            user = User.objects.get(username=username)
            user.first_name = first_name
            user.last_name  = last_name
            user.email      = email
            user.nombre_completo = f'{first_name} {last_name}'.strip()
            user.rol         = 'ADMIN'
            user.is_staff    = True
            user.is_superuser = True
            user.is_active   = True
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Usuario '{username}' actualizado (id={user.id})."
            ))
        else:
            user = User.objects.create_superuser(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                rol='ADMIN',
            )
            self.stdout.write(self.style.SUCCESS(
                f"Admin '{username}' creado correctamente (id={user.id}).\n"
                f"  Nombre completo: {user.nombre_completo}"
            ))
