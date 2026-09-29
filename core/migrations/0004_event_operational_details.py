from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core','0003_create_test_events')]

    operations = [
        migrations.AddField(model_name='event',name='food_info',field=models.CharField(blank=True,help_text='Ex.: buffet incluso, venda no local ou não incluso.',max_length=500,verbose_name='alimentação')),
        migrations.AddField(model_name='event',name='drinks_info',field=models.CharField(blank=True,help_text='Ex.: open bar, venda no local ou não incluso.',max_length=500,verbose_name='bebidas')),
        migrations.AddField(model_name='event',name='parking_info',field=models.CharField(blank=True,help_text='Informe se há estacionamento, valor ou orientação de acesso.',max_length=500,verbose_name='estacionamento')),
    ]
