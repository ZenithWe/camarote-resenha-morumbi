from django.core.management.base import BaseCommand
from core.models import SiteSettings
class Command(BaseCommand):
    help='Cria somente as configurações iniciais. Não cria usuários, vendas ou eventos fictícios.'
    def handle(self,*args,**options):
        _,created=SiteSettings.objects.get_or_create(pk=1)
        self.stdout.write(self.style.SUCCESS('Configuração inicial criada.' if created else 'Configuração existente preservada.'))
