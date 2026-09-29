from django.db import migrations, models
import core.models

class Migration(migrations.Migration):
    dependencies=[('core','0008_banner_mobile_image')]
    operations=[
        migrations.AlterField(
            model_name='banner',
            name='image',
            field=models.ImageField(upload_to=core.models.upload_path,verbose_name='imagem para computador'),
        ),
    ]
