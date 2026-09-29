from django.db import migrations, models
import core.models

class Migration(migrations.Migration):
    dependencies=[('core','0007_testimonial')]
    operations=[
        migrations.AddField(
            model_name='banner',
            name='mobile_image',
            field=models.ImageField(blank=True,upload_to=core.models.upload_path,verbose_name='imagem para celular'),
        ),
    ]
