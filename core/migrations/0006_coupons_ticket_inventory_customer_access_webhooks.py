from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
from decimal import Decimal
from django.utils import timezone
import core.models

class Migration(migrations.Migration):
    dependencies=[('core','0005_order_pagarme_fields')]
    operations=[
        migrations.CreateModel(
            name='Coupon',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('code',models.CharField(max_length=40,unique=True,verbose_name='código')),
                ('discount_type',models.CharField(choices=[('percent','Percentual'),('fixed','Valor fixo')],default='percent',max_length=10,verbose_name='tipo de desconto')),
                ('value',models.DecimalField(decimal_places=2,max_digits=10,validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],verbose_name='valor')),
                ('max_uses',models.PositiveIntegerField(default=100,validators=[django.core.validators.MinValueValidator(1)],verbose_name='limite de usos')),
                ('valid_from',models.DateTimeField(default=timezone.now,verbose_name='válido a partir de')),
                ('valid_until',models.DateTimeField(blank=True,null=True,verbose_name='válido até')),
                ('active',models.BooleanField(default=True,verbose_name='ativo')),
                ('created_at',models.DateTimeField(auto_now_add=True)),
                ('event',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.CASCADE,related_name='coupons',to='core.event')),
            ],
            options={'ordering':['code']},
        ),
        migrations.AddField(model_name='order',name='discount_amount',field=models.DecimalField(decimal_places=2,default=0,max_digits=12,validators=[django.core.validators.MinValueValidator(0)])),
        migrations.AddField(model_name='order',name='coupon',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='orders',to='core.coupon')),
        migrations.CreateModel(
            name='CustomerLoginCode',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('email',models.EmailField(db_index=True,max_length=254)),
                ('code_hash',models.CharField(max_length=64)),
                ('expires_at',models.DateTimeField()),
                ('attempts',models.PositiveSmallIntegerField(default=0)),
                ('used_at',models.DateTimeField(blank=True,null=True)),
                ('created_at',models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering':['-created_at']},
        ),
        migrations.CreateModel(
            name='WebhookLog',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('provider',models.CharField(max_length=30)),
                ('external_id',models.CharField(blank=True,max_length=100)),
                ('event_type',models.CharField(blank=True,max_length=80)),
                ('status',models.CharField(default='received',max_length=30)),
                ('detail',models.CharField(blank=True,max_length=240)),
                ('created_at',models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering':['-created_at']},
        ),
        migrations.CreateModel(
            name='EventTicket',
            fields=[
                ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
                ('file',models.FileField(storage=core.models.private_storage,upload_to=core.models.ticket_path,verbose_name='ingresso oficial')),
                ('label',models.CharField(blank=True,max_length=80,verbose_name='identificação')),
                ('assigned_at',models.DateTimeField(blank=True,null=True)),
                ('created_at',models.DateTimeField(auto_now_add=True)),
                ('event',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='ticket_inventory',to='core.event')),
                ('order',models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='assigned_tickets',to='core.order')),
            ],
            options={'ordering':['id']},
        ),
    ]
