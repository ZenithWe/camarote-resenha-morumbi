from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('core','0004_event_operational_details')]
    operations=[
        migrations.AddField(model_name='order',name='customer_document',field=models.CharField(blank=True,max_length=20)),
        migrations.AddField(model_name='order',name='payment_provider',field=models.CharField(default='manual',max_length=20)),
        migrations.AddField(model_name='order',name='provider_order_id',field=models.CharField(blank=True,max_length=80)),
        migrations.AddField(model_name='order',name='provider_charge_id',field=models.CharField(blank=True,max_length=80)),
        migrations.AddField(model_name='order',name='provider_transaction_id',field=models.CharField(blank=True,max_length=80)),
        migrations.AddField(model_name='order',name='provider_status',field=models.CharField(blank=True,max_length=40)),
        migrations.AddField(model_name='order',name='provider_pix_code',field=models.TextField(blank=True)),
        migrations.AddField(model_name='order',name='provider_expires_at',field=models.DateTimeField(blank=True,null=True)),
    ]
