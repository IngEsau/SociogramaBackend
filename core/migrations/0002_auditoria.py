from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Auditoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accion', models.CharField(choices=[
                    ('IMPORTACION', 'Importación masiva Excel'),
                    ('CREAR_GRUPO', 'Crear grupo'),
                    ('EDITAR_GRUPO', 'Editar grupo'),
                    ('CREAR_DIVISION', 'Crear división'),
                    ('EDITAR_DIVISION', 'Editar división'),
                    ('CREAR_PROGRAMA', 'Crear programa'),
                    ('EDITAR_PROGRAMA', 'Editar programa'),
                    ('EDITAR_PERIODO', 'Editar periodo'),
                    ('EDITAR_USUARIO', 'Editar usuario'),
                    ('ACTIVAR_USUARIO', 'Activar usuario'),
                    ('DESACTIVAR_USUARIO', 'Desactivar usuario'),
                    ('ASIGNAR_TUTOR', 'Asignar tutor a grupo'),
                ], max_length=30)),
                ('entidad', models.CharField(max_length=50)),
                ('entidad_id', models.IntegerField(blank=True, null=True)),
                ('detalle', models.JSONField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(
                    db_column='usuario_id',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='auditorias',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Auditoría',
                'verbose_name_plural': 'Auditorías',
                'db_table': 'auditorias',
                'ordering': ['-timestamp'],
                'managed': True,
            },
        ),
    ]
