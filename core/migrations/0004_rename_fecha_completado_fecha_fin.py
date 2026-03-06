from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_crear_usuario_auditoria_choice'),
    ]

    operations = [
        migrations.RenameField(
            model_name='cuestionarioestado',
            old_name='fecha_completado',
            new_name='fecha_fin',
        ),
    ]
