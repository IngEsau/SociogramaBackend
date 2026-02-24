from core.models import User

User.objects.create_user(
    username='comite_test',
    email='comite@test.utpuebla.edu.mx',
    password='comite_test',
    first_name='Comité',
    last_name='Prueba',
    rol='COMITE',
    nombre_completo='Comité Prueba',
    is_active=True,
    is_staff=False,
)

print("Listo!")