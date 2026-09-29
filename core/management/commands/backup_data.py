import json
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.utils import timezone
from core.models import Event, Order, Expense, Coupon, Testimonial, EventTicket, SiteSettings

class Command(BaseCommand):
    help='Cria um backup JSON sem senhas, CPF ou credenciais e salva no armazenamento privado.'

    def handle(self,*args,**options):
        cfg=SiteSettings.objects.filter(pk=1).first()
        data={
            'generated_at':timezone.now().isoformat(),
            'version':2,
            'site':{
                'texts':cfg.texts if cfg else {},
                'instagram':cfg.instagram if cfg else '',
                'whatsapp':cfg.whatsapp if cfg else '',
                'contact_email':cfg.contact_email if cfg else '',
                'sales_enabled':cfg.sales_enabled if cfg else False,
            },
            'events':[{
                'id':str(x.pk),'title':x.title,'description':x.description,'category':x.category,
                'starts_at':x.starts_at.isoformat(),'doors_at':x.doors_at.isoformat() if x.doors_at else None,
                'price':str(x.price),'capacity':x.capacity,'max_per_order':x.max_per_order,'status':x.status,
                'location':x.location,'includes':x.includes,'food_info':x.food_info,'drinks_info':x.drinks_info,
                'parking_info':x.parking_info,'age_rules':x.age_rules,
            } for x in Event.objects.all()],
            'orders':[{
                'id':str(x.pk),'code':x.code,'event_id':str(x.event_id),'customer_name':x.customer_name,
                'email':x.email,'phone':x.phone,'quantity':x.quantity,'unit_price':str(x.unit_price),
                'total':str(x.total),'discount_amount':str(x.discount_amount),'coupon':x.coupon.code if x.coupon_id else None,
                'status':x.status,'payment_provider':x.payment_provider,'provider_status':x.provider_status,
                'created_at':x.created_at.isoformat(),'paid_at':x.paid_at.isoformat() if x.paid_at else None,
            } for x in Order.objects.select_related('coupon').all()],
            'expenses':[{'description':x.description,'amount':str(x.amount),'kind':x.kind,'date':x.date.isoformat()} for x in Expense.objects.all()],
            'coupons':[{'code':x.code,'discount_type':x.discount_type,'value':str(x.value),'max_uses':x.max_uses,'active':x.active} for x in Coupon.objects.all()],
            'testimonials':[{'name':x.name,'text':x.text,'active':x.active,'position':x.position} for x in Testimonial.objects.all()],
            'ticket_inventory':[{'event_id':str(x.event_id),'label':x.label,'assigned_order_code':x.order.code if x.order_id else None} for x in EventTicket.objects.select_related('order').all()],
        }
        raw=json.dumps(data,ensure_ascii=False,indent=2).encode('utf-8')
        stamp=timezone.localtime().strftime('%Y%m%d-%H%M%S')
        path=f'backups/resenha-{stamp}.json'
        storage=storages['private']
        saved=storage.save(path,ContentFile(raw))
        self.stdout.write(self.style.SUCCESS(f'Backup criado: {saved}'))
