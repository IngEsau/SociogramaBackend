from rest_framework import serializers
from django.contrib.auth import authenticate
from core.models import User, Alumno  


class UserSerializer(serializers.ModelSerializer):
    """Serializador para el modelo User extendido"""
    nombre_completo = serializers.CharField(read_only=True)  
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'nombre_completo', 'rol', 'genero', 'telefono',  
            'fecha_nacimiento', 'is_staff', 'is_active'
        ]
        read_only_fields = ['id', 'is_staff', 'nombre_completo']


class LoginSerializer(serializers.Serializer):
    """Serializador para login (matrícula o username + password)"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        if username and password:
            # Intentar autenticar con username
            user = authenticate(username=username, password=password)
            
            # Si no funciona, intentar buscar por matrícula
            if not user:
                try:
                    alumno = Alumno.objects.select_related('user').get(matricula=username)
                    user = authenticate(username=alumno.user.username, password=password)
                except Alumno.DoesNotExist:
                    pass
            
            if not user:
                raise serializers.ValidationError('Credenciales inválidas')
            
            if not user.is_active:
                raise serializers.ValidationError('Usuario inactivo')
            
            data['user'] = user
        else:
            raise serializers.ValidationError('Debe proporcionar username y password')
        
        return data


class RegisterSerializer(serializers.ModelSerializer):
    """Serializador para registro de nuevos usuarios"""
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, label='Confirmar Password', style={'input_type': 'password'})
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2', 
            'first_name', 'last_name', 'rol', 'genero', 'telefono' 
        ]
    
    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Las contraseñas no coinciden'})
        return data
    
    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializador para solicitar reset de contraseña"""
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """Validar que el email exista en el sistema"""
        try:
            User.objects.get(email=value, is_active=True)
        except User.DoesNotExist:
            # Por seguridad, no revelamos si el email existe o no
            # pero internamente validamos
            pass
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializador para confirmar reset de contraseña"""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True, 
        write_only=True,
        min_length=8,
        style={'input_type': 'password'}
    )
    new_password2 = serializers.CharField(
        required=True,
        write_only=True,
        label='Confirmar Password',
        style={'input_type': 'password'}
    )
    
    def validate(self, data):
        """Validar que las contraseñas coincidan"""
        if data['new_password'] != data['new_password2']:
            raise serializers.ValidationError({
                'new_password2': 'Las contraseñas no coinciden'
            })
        
        # Validar longitud mínima
        if len(data['new_password']) < 8:
            raise serializers.ValidationError({
                'new_password': 'La contraseña debe tener al menos 8 caracteres'
            })
        
        return data