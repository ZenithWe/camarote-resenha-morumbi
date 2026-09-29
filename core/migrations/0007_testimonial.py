from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('core','0006_coupons_ticket_inventory_customer_access_webhooks')]
    operations=[
        migrations.CreateModel(
            name='Testimonial',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('name',models.CharField(max_length=100,verbose_name='nome')),
                ('text',models.CharField(max_length=600,verbose_name='depoimento')),
                ('active',models.BooleanField(default=True,verbose_name='exibir no site')),
                ('position',models.PositiveSmallIntegerField(default=0,verbose_name='ordem')),
                ('created_at',models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering':['position','id']},
        ),
    ]
