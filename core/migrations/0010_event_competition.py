from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[
        ('core','0009_banner_desktop_label'),
    ]

    operations=[
        migrations.AddField(
            model_name='event',
            name='competition',
            field=models.CharField(
                blank=True,
                choices=[
                    ('brasileirao','Campeonato Brasileiro'),
                    ('copa_do_brasil','Copa do Brasil'),
                    ('libertadores','CONMEBOL Libertadores'),
                    ('sul_americana','CONMEBOL Sul-Americana'),
                    ('paulista','Campeonato Paulista'),
                    ('supercopa','Supercopa Rei'),
                    ('recopa','Recopa Sul-Americana'),
                    ('mundial','Mundial de Clubes'),
                    ('amistoso','Amistoso'),
                    ('outra','Outra competição'),
                ],
                max_length=24,
                verbose_name='competição',
            ),
        ),
    ]
