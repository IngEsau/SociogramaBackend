"""
Management command para hacer backup de la base de datos.

Uso:
    python manage.py backup_db              # backup completo con dumpdata
    python manage.py backup_db --app core   # solo una app
    python manage.py backup_db --mysql      # usando mysqldump (requiere mysql en PATH)
"""
import os
import subprocess
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Genera un backup de la base de datos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            default=None,
            help='Limitar backup a una app específica (ej: core)'
        )
        parser.add_argument(
            '--mysql',
            action='store_true',
            help='Usar mysqldump en lugar de dumpdata (requiere mysql en PATH)'
        )
        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='Ruta de salida del archivo (por defecto: database/backups/)'
        )

    def handle(self, *args, **options):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = options['output'] or os.path.join('database', 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        if options['mysql']:
            self._backup_mysqldump(backup_dir, timestamp)
        else:
            self._backup_dumpdata(backup_dir, timestamp, options['app'])

    def _backup_dumpdata(self, backup_dir, timestamp, app=None):
        target = app or 'all'
        filename = f'backup_{target}_{timestamp}.json'
        filepath = os.path.join(backup_dir, filename)

        args = ['dumpdata', '--indent', '2', '--output', filepath]
        if app:
            args.append(app)

        from django.core.management import call_command
        call_command(*args)

        size = os.path.getsize(filepath) / 1024
        self.stdout.write(
            self.style.SUCCESS(f'Backup guardado: {filepath} ({size:.1f} KB)')
        )

    def _backup_mysqldump(self, backup_dir, timestamp):
        db = settings.DATABASES['default']
        filename = f'backup_mysql_{timestamp}.sql'
        filepath = os.path.join(backup_dir, filename)

        cmd = [
            'mysqldump',
            f'-u{db["USER"]}',
            f'-p{db["PASSWORD"]}',
            f'-h{db.get("HOST", "127.0.0.1")}',
            db['NAME'],
        ]

        try:
            with open(filepath, 'w') as f:
                subprocess.run(cmd, stdout=f, check=True)
            size = os.path.getsize(filepath) / 1024
            self.stdout.write(
                self.style.SUCCESS(f'Backup MySQL guardado: {filepath} ({size:.1f} KB)')
            )
        except FileNotFoundError:
            self.stderr.write(
                self.style.ERROR('mysqldump no encontrado en PATH. Usa sin --mysql para usar dumpdata.')
            )
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f'Error en mysqldump: {e}'))
