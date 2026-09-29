import hashlib, unicodedata
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Event, Order, SiteSettings, AuditLog

def log(user,action,obj=''):
    AuditLog.objects.create(user=user,action=action,object_id=str(obj))

def occupied(event):
    return event.orders.filter(Q(status__in=['paid','review'])|Q(status='pending',expires_at__gt=timezone.now())).aggregate(n=Sum('quantity'))['n'] or 0

def fingerprint(request):
    return hashlib.sha256((settings.SECRET_KEY+request.META.get('REMOTE_ADDR','')).encode()).hexdigest()

@transaction.atomic
def create_order(data,ip_hash):
    # Lock the event before checking stock. Every stock-changing operation uses this same lock.
    event=Event.objects.select_for_update().get(pk=data['event_id'])
    existing=Order.objects.filter(request_key=data['request_key']).first()
    if existing: return existing
    cfg=SiteSettings.objects.get(pk=1)
    if not cfg.sales_enabled or not all([cfg.pix_key,cfg.pix_name,cfg.pix_city]): raise ValidationError('As vendas estão pausadas. Tente novamente mais tarde.')
    if event.status!='published' or event.is_past: raise ValidationError('Este evento não está disponível para compra.')
    quantity=data['quantity']
    if quantity<1 or quantity>event.max_per_order: raise ValidationError(f'O limite por pedido é de {event.max_per_order} ingressos.')
    if quantity>event.capacity-occupied(event): raise ValidationError('Não há ingressos suficientes. Atualize a quantidade.')
    recent=Order.objects.filter(created_at__gte=timezone.now()-timedelta(hours=1)).filter(Q(ip_hash=ip_hash)|Q(email__iexact=data['email'])).count()
    if recent>=8: raise ValidationError('Limite temporário de pedidos. Aguarde uma hora ou entre em contato com a equipe.')
    return Order.objects.create(event=event,customer_name=data['customer_name'],email=data['email'].lower(),phone=data['phone'],quantity=quantity,unit_price=event.price,total=event.price*quantity,expires_at=timezone.now()+timedelta(minutes=30),request_key=data['request_key'],ip_hash=ip_hash,pix_snapshot={'key':cfg.pix_key,'name':cfg.pix_name,'city':cfg.pix_city})

@transaction.atomic
def change_order(order_id,new_status,user,fee=Decimal('0')):
    event_id=Order.objects.values_list('event_id',flat=True).get(pk=order_id)
    event=Event.objects.select_for_update().get(pk=event_id)
    order=Order.objects.select_for_update().get(pk=order_id)
    transitions={'pending':{'paid','cancelled'},'review':{'paid','cancelled'},'paid':{'refunded'},'cancelled':set(),'refunded':set()}
    if new_status not in transitions.get(order.status,set()): raise ValidationError('Esta alteração não está disponível para a situação atual do pedido.')
    if new_status=='paid':
        if order.expired and occupied(event)+order.quantity>event.capacity: raise ValidationError('A reserva expirou e o estoque é insuficiente. Não confirme sem resolver a disponibilidade.')
        if fee<0 or fee>order.total: raise ValidationError('Informe uma taxa entre zero e o total do pedido.')
        order.paid_at=timezone.now(); order.fee=fee
    if new_status=='refunded': order.refunded_at=timezone.now()
    order.status=new_status; order.save()
    log(user,f'Pedido {order.code}: {new_status}',order.pk)
    return order

@transaction.atomic
def report_receipt(order_id,receipt):
    event_id=Order.objects.values_list('event_id',flat=True).get(pk=order_id)
    Event.objects.select_for_update().get(pk=event_id)
    order=Order.objects.select_for_update().get(pk=order_id)
    if order.status!='pending' or order.expired: raise ValidationError('O prazo desta reserva terminou ou o pedido já foi atualizado. Entre em contato com a equipe se você pagou.')
    order.receipt=receipt; order.status='review'; order.reported_at=timezone.now(); order.save()
    return order

def pix_payload(order):
    def field(id,val): return id+str(len(val.encode('utf-8'))).zfill(2)+val
    def ascii_text(value,length): return unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().upper()[:length]
    p=order.pix_snapshot
    merchant=field('00','BR.GOV.BCB.PIX')+field('01',p['key'])
    payload=field('00','01')+field('26',merchant)+field('52','0000')+field('53','986')+field('54',f'{order.total:.2f}')+field('58','BR')+field('59',ascii_text(p['name'],25))+field('60',ascii_text(p['city'],15))+field('62',field('05',order.code))+'6304'
    crc=0xFFFF
    for byte in payload.encode('utf-8'):
        crc^=byte<<8
        for _ in range(8): crc=((crc<<1)^0x1021)&0xFFFF if crc&0x8000 else (crc<<1)&0xFFFF
    return payload+f'{crc:04X}'
