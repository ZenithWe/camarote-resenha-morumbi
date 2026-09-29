import secrets
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from core.models import SiteSettings

class Command(BaseCommand):
    help = 'Cria as configurações iniciais e, somente se necessário, um administrador temporário.'

    def handle(self, *args, **options):
        _, created = SiteSettings.objects.get_or_create(pk=1)
        self.stdout.write(self.style.SUCCESS(
            'Configuração inicial criada.' if created else 'Configuração existente preservada.'
        ))

        User = get_user_model()
        if not User.objects.filter(is_superuser=True, is_active=True).exists():
            username = 'admin'
            password = secrets.token_urlsafe(16)
            email = 'admin@resenhamorumbi.local'

            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )

            self.stdout.write(self.style.WARNING('ADM_TEMP_CRIADO=1'))
            self.stdout.write(f'ADM_TEMP_USERNAME={user.username}')
            self.stdout.write(f'ADM_TEMP_PASSWORD={password}')
            self.stdout.write(self.style.WARNING(
                'Troque a senha após o primeiro acesso. Este usuário só é criado se não existir superusuário ativo.'
            ))
        else:
            self.stdout.write('Administrador existente preservado.')
