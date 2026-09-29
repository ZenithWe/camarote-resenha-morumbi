import hashlib, hmac, unicodedata, json, urllib.request, urllib.error, base64
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Event, Order, SiteSettings, AuditLog


def mercadopago_request(method,path,payload=None,idempotency_key=None):
    if not getattr(settings,'MERCADOPAGO_CONFIGURED',False):
        raise ValidationError('Mercado Pago ainda não está configurado.')
    headers={'Authorization':f'Bearer {settings.MERCADOPAGO_ACCESS_TOKEN}','Accept':'application/json'}
    if idempotency_key: headers['X-Idempotency-Key']=str(idempotency_key)
    body=None
    if payload is not None:
        body=json.dumps(payload).encode('utf-8')
        headers['Content-Type']='application/json'
    request=urllib.request.Request(f"{settings.MERCADOPAGO_API_BASE}{path}",data=body,method=method,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=15) as response:
            raw=response.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as exc:
        raise ValidationError('Não foi possível comunicar com o Mercado Pago. Tente novamente em instantes.') from exc

def validate_mercadopago_webhook(x_signature,x_request_id,data_id):
    secret=getattr(settings,'MERCADOPAGO_WEBHOOK_SECRET','')
    if not secret: return True
    if not x_signature or not x_request_id or not data_id: return False
    parts={}
    for item in x_signature.split(','):
        if '=' in item:
            key,value=item.split('=',1)
            parts[key.strip()]=value.strip()
    ts=parts.get('ts'); received=parts.get('v1')
    if not ts or not received: return False
    manifest=f"id:{str(data_id).lower()};request-id:{x_request_id};ts:{ts};"
    expected=hmac.new(secret.encode('utf-8'),manifest.encode('utf-8'),hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,received)

def initialize_mercadopago_pix(order):
    if order.payment_provider!='mercadopago': return order
    names=order.customer_name.strip().split(' ',1)
    payer={
        'email':order.email,
        'first_name':names[0][:60],
        'identification':{'type':'CPF','number':order.customer_document},
    }
    if len(names)>1: payer['last_name']=names[1][:60]
    payload={
        'transaction_amount':float(order.total),
        'description':order.event.title[:255],
        'payment_method_id':'pix',
        'date_of_expiration':timezone.localtime(timezone.now()+timedelta(minutes=31)).isoformat(),
        'external_reference':str(order.pk),
        'notification_url':f"{settings.SITE_URL}/webhooks/mercadopago/",
        'payer':payer,
    }
    response=mercadopago_request('POST','/v1/payments',payload,idempotency_key=order.request_key)
    transaction_data=((response.get('point_of_interaction') or {}).get('transaction_data') or {})
    qr_code=transaction_data.get('qr_code') or ''
    payment_id=response.get('id')
    if not payment_id or not qr_code:
        raise ValidationError('O Mercado Pago não retornou um Pix válido para este pedido.')
    expires=parse_datetime(response.get('date_of_expiration') or '') if response.get('date_of_expiration') else None
    order.provider_order_id=str(payment_id)
    order.provider_status=(response.get('status') or 'pending').lower()
    order.provider_pix_code=qr_code
    if expires:
        order.provider_expires_at=expires
        if expires<order.expires_at: order.expires_at=expires
    order.save(update_fields=['provider_order_id','provider_status','provider_pix_code','provider_expires_at','expires_at'])
    return order

def sync_mercadopago_payment(order_id,payment_id=None):
    event_id=Order.objects.values_list('event_id',flat=True).get(pk=order_id)
    with transaction.atomic():
        event=Event.objects.select_for_update().get(pk=event_id)
        order=Order.objects.select_for_update().get(pk=order_id)
        if order.payment_provider!='mercadopago': return order
        target=str(payment_id or order.provider_order_id or '')
        if not target: return order
        payment=mercadopago_request('GET',f"/v1/payments/{target}")
        expected=order.total.quantize(Decimal('0.01'))
        received=Decimal(str(payment.get('transaction_amount') or '0')).quantize(Decimal('0.01'))
        external_reference=str(payment.get('external_reference') or '')
        method=str(payment.get('payment_method_id') or '')
        if received!=expected or external_reference!=str(order.pk) or method!='pix':
            order.provider_status='verification_failed'
            order.save(update_fields=['provider_status'])
            log(None,'Mercado Pago: divergência na verificação',order.pk)
            return order
        if not order.provider_order_id:
            order.provider_order_id=str(payment.get('id') or target)
        status=(payment.get('status') or '').lower()
        order.provider_status=status
        notify=None
        if status=='approved' and order.status in ['pending','review']:
            if order.expired and occupied(event)+order.quantity>event.capacity:
                order.status='review'
                log(None,'Mercado Pago pago com estoque para revisão',order.pk)
            else:
                order.status='paid'
                order.paid_at=timezone.now()
                notify='paid'
                log(None,'Mercado Pago confirmou pagamento',order.pk)
        elif status in ['rejected','cancelled','canceled'] and order.status in ['pending','review']:
            order.status='cancelled'
            notify='cancelled'
            log(None,'Mercado Pago informou falha/cancelamento',order.pk)
        elif status in ['refunded','charged_back'] and order.status=='paid':
            order.status='refunded'
            order.refunded_at=timezone.now()
            notify='refunded'
            log(None,'Mercado Pago confirmou estorno',order.pk)
        order.save(update_fields=['provider_order_id','provider_status','status','paid_at','refunded_at'])
        if notify: transaction.on_commit(lambda oid=order.pk,kind=notify: notify_order(oid,kind))
        return order

def pagarme_request(method,path,payload=None):
    if not getattr(settings,'PAGARME_CONFIGURED',False):
        raise ValidationError('Pagar.me ainda não está configurado.')
    credentials=base64.b64encode(f"{settings.PAGARME_SECRET_KEY}:".encode('utf-8')).decode('ascii')
    headers={'Authorization':f'Basic {credentials}','Accept':'application/json'}
    body=None
    if payload is not None:
        body=json.dumps(payload).encode('utf-8')
        headers['Content-Type']='application/json'
    request=urllib.request.Request(f"{settings.PAGARME_API_BASE}{path}",data=body,method=method,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=15) as response:
            raw=response.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as exc:
        raise ValidationError('Não foi possível comunicar com o Pagar.me. Tente novamente em instantes.') from exc

def initialize_pagarme_pix(order):
    if order.payment_provider!='pagarme': return order
    phone=''.join(ch for ch in order.phone if ch.isdigit())
    if phone.startswith('55'): phone=phone[2:]
    area_code=phone[:2]
    number=phone[2:]
    if len(area_code)!=2 or len(number) not in [8,9]:
        raise ValidationError('O telefone informado não pôde ser enviado ao Pagar.me.')
    unit_amount=int((order.unit_price*100).quantize(Decimal('1')))
    payload={
        'code':str(order.pk),
        'items':[{
            'amount':unit_amount,
            'description':order.event.title[:255],
            'quantity':order.quantity,
            'code':str(order.event_id)[:52],
        }],
        'customer':{
            'name':order.customer_name[:64],
            'email':order.email[:64],
            'type':'individual',
            'document':order.customer_document,
            'phones':{
                'mobile_phone':{
                    'country_code':'55',
                    'area_code':area_code,
                    'number':number,
                }
            },
        },
        'payments':[{
            'payment_method':'pix',
            'pix':{
                'expires_in':1800,
                'additional_information':[
                    {'name':'Pedido','value':order.code},
                    {'name':'Evento','value':order.event.title[:50]},
                ],
            },
        }],
        'closed':True,
    }
    response=pagarme_request('POST','/orders',payload)
    charges=response.get('charges') or []
    charge=charges[0] if charges else {}
    transaction_data=charge.get('last_transaction') or {}
    qr_code=transaction_data.get('qr_code') or ''
    if not response.get('id') or not charge.get('id') or not qr_code:
        raise ValidationError('O Pagar.me não retornou um Pix válido para este pedido.')
    expires=parse_datetime(transaction_data.get('expires_at') or '') if transaction_data.get('expires_at') else None
    order.provider_order_id=response.get('id','')
    order.provider_charge_id=charge.get('id','')
    order.provider_transaction_id=transaction_data.get('id','')
    order.provider_status=(charge.get('status') or response.get('status') or 'pending').lower()
    order.provider_pix_code=qr_code
    if expires:
        order.provider_expires_at=expires
        if expires<order.expires_at: order.expires_at=expires
    order.save(update_fields=['provider_order_id','provider_charge_id','provider_transaction_id','provider_status','provider_pix_code','provider_expires_at','expires_at'])
    return order

def sync_pagarme_charge(order_id):
    event_id=Order.objects.values_list('event_id',flat=True).get(pk=order_id)
    with transaction.atomic():
        event=Event.objects.select_for_update().get(pk=event_id)
        order=Order.objects.select_for_update().get(pk=order_id)
        if order.payment_provider!='pagarme' or not order.provider_charge_id: return order
        charge=pagarme_request('GET',f"/charges/{order.provider_charge_id}")
        expected=int((order.total*100).quantize(Decimal('1')))
        if int(charge.get('amount') or 0)!=expected:
            order.provider_status='amount_mismatch'
            order.save(update_fields=['provider_status'])
            log(None,'Pagar.me: divergência de valor',order.pk)
            return order
        status=(charge.get('status') or '').lower()
        order.provider_status=status
        notify=None
        if status=='paid' and order.status in ['pending','review']:
            if order.expired and occupied(event)+order.quantity>event.capacity:
                order.status='review'
                log(None,'Pagar.me pago com estoque para revisão',order.pk)
            else:
                order.status='paid'
                order.paid_at=timezone.now()
                notify='paid'
                log(None,'Pagar.me confirmou pagamento',order.pk)
        elif status in ['failed','canceled','cancelled'] and order.status in ['pending','review']:
            order.status='cancelled'
            notify='cancelled'
            log(None,'Pagar.me informou falha/cancelamento',order.pk)
        elif status=='refunded' and order.status=='paid':
            order.status='refunded'
            order.refunded_at=timezone.now()
            notify='refunded'
            log(None,'Pagar.me confirmou estorno',order.pk)
        order.save(update_fields=['provider_status','status','paid_at','refunded_at'])
        if notify: transaction.on_commit(lambda oid=order.pk,kind=notify: notify_order(oid,kind))
        return order

def send_whatsapp_notification(phone,body):
    if not getattr(settings,'WHATSAPP_NOTIFICATIONS_ENABLED',False): return False
    try:
        payload=json.dumps({'messaging_product':'whatsapp','to':phone,'type':'text','text':{'body':body}}).encode('utf-8')
        request=urllib.request.Request(settings.WHATSAPP_API_URL,data=payload,method='POST',headers={'Authorization':f'Bearer {settings.WHATSAPP_API_TOKEN}','Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=8) as response:
            return 200 <= response.status < 300
    except Exception:
        return False

def notify_order(order_id,kind):
    if not (getattr(settings,'EMAIL_NOTIFICATIONS_ENABLED',False) or getattr(settings,'WHATSAPP_NOTIFICATIONS_ENABLED',False)): return False
    try:
        order=Order.objects.select_related('event').get(pk=order_id)
        url=f"{settings.SITE_URL}/pedido/{order.access_token}/"
        created_body=(f'Sua reserva para {order.event.title} foi criada. O pedido {order.code} fica reservado até {timezone.localtime(order.expires_at).strftime("%d/%m/%Y %H:%M")}. Pague o Pix e acompanhe a confirmação automática em: {url}' if order.payment_provider in ['pagarme','mercadopago'] else f'Sua reserva para {order.event.title} foi criada. O pedido {order.code} fica reservado até {timezone.localtime(order.expires_at).strftime("%d/%m/%Y %H:%M")}. Acompanhe e envie o comprovante em: {url}')
        messages={
            'created':('Reserva criada',created_body),
            'review':('Comprovante recebido',f'Recebemos o comprovante do pedido {order.code}. O pagamento está em análise. Acompanhe em: {url}'),
            'paid':('Pagamento confirmado',f'O pagamento do pedido {order.code} para {order.event.title} foi confirmado. O ingresso oficial será disponibilizado na página do pedido: {url}'),
            'cancelled':('Pedido cancelado',f'O pedido {order.code} foi cancelado. Se você já realizou o pagamento, entre em contato com a equipe. Consulte: {url}'),
            'refunded':('Reembolso registrado',f'O reembolso do pedido {order.code} foi registrado pela equipe. Consulte os detalhes em: {url}'),
            'ticket':('Ingresso disponível',f'Um ingresso oficial do pedido {order.code} já está disponível para download. Acesse a página privada do pedido: {url}'),
        }
        subject,body=messages.get(kind,('Atualização do pedido',f'Seu pedido {order.code} foi atualizado. Acompanhe em: {url}'))
        sent=False
        if getattr(settings,'EMAIL_NOTIFICATIONS_ENABLED',False):
            send_mail(f'Resenha Morumbi • {subject}',body,settings.DEFAULT_FROM_EMAIL,[order.email],fail_silently=True)
            sent=True
        if send_whatsapp_notification(order.phone,body): sent=True
        return sent
    except Exception:
        return False

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
    provider=getattr(settings,'PAYMENT_PROVIDER','manual')
    if provider=='pagarme': gateway_ready=getattr(settings,'PAGARME_CONFIGURED',False)
    elif provider=='mercadopago': gateway_ready=getattr(settings,'MERCADOPAGO_CONFIGURED',False)
    else: gateway_ready=all([cfg.pix_key,cfg.pix_name,cfg.pix_city])
    if not cfg.sales_enabled or not gateway_ready: raise ValidationError('As vendas estão pausadas. Tente novamente mais tarde.')
    if event.status!='published' or event.is_past: raise ValidationError('Este evento não está disponível para compra.')
    quantity=data['quantity']
    if quantity<1 or quantity>event.max_per_order: raise ValidationError(f'O limite por pedido é de {event.max_per_order} ingressos.')
    if quantity>event.capacity-occupied(event): raise ValidationError('Não há ingressos suficientes. Atualize a quantidade.')
    recent=Order.objects.filter(created_at__gte=timezone.now()-timedelta(hours=1)).filter(Q(ip_hash=ip_hash)|Q(email__iexact=data['email'])).count()
    if recent>=8: raise ValidationError('Limite temporário de pedidos. Aguarde uma hora ou entre em contato com a equipe.')
    order=Order.objects.create(event=event,customer_name=data['customer_name'],email=data['email'].lower(),phone=data['phone'],customer_document=data.get('document',''),payment_provider=provider,quantity=quantity,unit_price=event.price,total=event.price*quantity,expires_at=timezone.now()+timedelta(minutes=30),request_key=data['request_key'],ip_hash=ip_hash,pix_snapshot={'key':cfg.pix_key,'name':cfg.pix_name,'city':cfg.pix_city} if provider!='pagarme' else {})
    if provider=='pagarme': initialize_pagarme_pix(order)
    elif provider=='mercadopago': initialize_mercadopago_pix(order)
    transaction.on_commit(lambda: notify_order(order.pk,'created'))
    return order

@transaction.atomic
def change_order(order_id,new_status,user,fee=Decimal('0')):
    event_id=Order.objects.values_list('event_id',flat=True).get(pk=order_id)
    event=Event.objects.select_for_update().get(pk=event_id)
    order=Order.objects.select_for_update().get(pk=order_id)
    if order.payment_provider in ['pagarme','mercadopago']: raise ValidationError('O status deste pedido é controlado automaticamente pelo gateway de pagamento.')
    transitions={'pending':{'paid','cancelled'},'review':{'paid','cancelled'},'paid':{'refunded'},'cancelled':set(),'refunded':set()}
    if new_status not in transitions.get(order.status,set()): raise ValidationError('Esta alteração não está disponível para a situação atual do pedido.')
    if new_status=='paid':
        if order.expired and occupied(event)+order.quantity>event.capacity: raise ValidationError('A reserva expirou e o estoque é insuficiente. Não confirme sem resolver a disponibilidade.')
        if fee<0 or fee>order.total: raise ValidationError('Informe uma taxa entre zero e o total do pedido.')
        order.paid_at=timezone.now(); order.fee=fee
    if new_status=='refunded': order.refunded_at=timezone.now()
    order.status=new_status; order.save()
    log(user,f'Pedido {order.code}: {new_status}',order.pk)
    transaction.on_commit(lambda: notify_order(order.pk,new_status))
    return order

@transaction.atomic
def report_receipt(order_id,receipt):
    event_id=Order.objects.values_list('event_id',flat=True).get(pk=order_id)
    Event.objects.select_for_update().get(pk=event_id)
    order=Order.objects.select_for_update().get(pk=order_id)
    if order.payment_provider in ['pagarme','mercadopago']: raise ValidationError('Pedidos automáticos não usam envio de comprovante.')
    if order.status!='pending' or order.expired: raise ValidationError('O prazo desta reserva terminou ou o pedido já foi atualizado. Entre em contato com a equipe se você pagou.')
    order.receipt=receipt; order.status='review'; order.reported_at=timezone.now(); order.save()
    transaction.on_commit(lambda: notify_order(order.pk,'review'))
    return order

def pix_payload(order):
    if order.payment_provider in ['pagarme','mercadopago']: return order.provider_pix_code or ''
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
