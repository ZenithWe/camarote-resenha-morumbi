import calendar, csv, uuid, re, json
from io import BytesIO
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncMonth
from django.http import Http404, HttpResponse, FileResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from .models import Event, EventPhoto, Order, OrderTicket, Banner, SiteSettings, Expense, AuditLog
from .forms import EventForm, BannerForm, SettingsForm, MediaForm, ContentForm, CheckoutForm, ReceiptForm, ExpenseForm, TicketForm, clean_image
from .content import CONTENT, DEFAULT_TEXTS
from .services import create_order, change_order, report_receipt, pix_payload, fingerprint, log, occupied, notify_order, sync_pagarme_charge

operator_required=user_passes_test(lambda u:u.is_active and u.is_superuser,login_url='/painel/entrar/')
class PanelLoginView(LoginView):
    template_name='registration/login.html'
    redirect_authenticated_user=False
    def form_valid(self,form):
        if not form.get_user().is_superuser:
            form.add_error(None,'Esta conta não tem acesso ao painel.'); return self.form_invalid(form)
        return super().form_valid(form)

def health(request): return JsonResponse({'status':'ok'})
def home(request):
    category=request.GET.get('categoria','')
    upcoming=Event.objects.filter(status='published',starts_at__gt=timezone.now()).order_by('starts_at')
    upcoming_games=upcoming.filter(category='football')[:3]
    upcoming_shows=upcoming.filter(category='concert')[:3]
    events=Event.objects.filter(status='published',starts_at__gt=timezone.now()).prefetch_related('photos').order_by('-featured','starts_at')
    if category in ['football','concert']: events=events.filter(category=category)
    return render(request,'core/home.html',{
        'events':events,
        'category':category,
        'banners':Banner.objects.filter(active=True),
        'upcoming_games':upcoming_games,
        'upcoming_shows':upcoming_shows,
    })
def public_agenda(request):
    today=timezone.localdate()
    category=request.GET.get('categoria','')
    if category not in ['football','concert']: category=''
    try:
        year=int(request.GET.get('ano',today.year)); month=int(request.GET.get('mes',today.month))
        if not 2020<=year<=2100 or not 1<=month<=12: raise ValueError
    except ValueError:
        year,month=today.year,today.month
    first=date(year,month,1)
    next_month=date(year+1,1,1) if month==12 else date(year,month+1,1)
    prev_date=first-timedelta(days=1)
    qs=Event.objects.filter(status='published',starts_at__date__gte=first,starts_at__date__lt=next_month).order_by('starts_at')
    if first.year==today.year and first.month==today.month:
        qs=qs.filter(starts_at__gte=timezone.now())
    if category: qs=qs.filter(category=category)
    events=list(qs)
    event_days={}
    for event in events:
        event_days.setdefault(timezone.localdate(event.starts_at),[]).append(event)
    weeks=[]
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year,month):
        weeks.append([{'date':day,'current':day.month==month,'today':day==today,'events':event_days.get(day,[])} for day in week])
    month_name=['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'][month-1]
    return render(request,'core/agenda.html',{
        'events':events,'weeks':weeks,'month_name':month_name,'year':year,'month':month,'category':category,
        'next_year':next_month.year,'next_month':next_month.month,'prev_year':prev_date.year,'prev_month':prev_date.month,
    })

def event_detail(request,pk):
    event=get_object_or_404(Event,pk=pk,status='published')
    return render(request,'core/event.html',{'event':event})
def terms(request): return render(request,'core/terms.html')

def public_image(request,path):
    if not re.fullmatch(r'images/[a-f0-9]{32}\.webp',path): raise Http404
    if not default_storage.exists(path): raise Http404
    response=FileResponse(default_storage.open(path,'rb'),content_type='image/webp')
    response['Cache-Control']='public, max-age=86400'
    response['X-Content-Type-Options']='nosniff'
    return response

@never_cache
def checkout(request,pk):
    event=get_object_or_404(Event,pk=pk,status='published')
    session_key=f'checkout_{pk}'
    if request.method=='GET' or session_key not in request.session: request.session[session_key]=str(uuid.uuid4())
    form=CheckoutForm(request.POST or None,initial={'request_key':request.session[session_key]},require_document=getattr(settings,'PAYMENT_PROVIDER','manual')=='pagarme')
    form.fields['quantity'].max_value=event.max_per_order
    form.fields['quantity'].widget.attrs.update({'min':1,'max':event.max_per_order})
    if request.method=='POST' and form.is_valid():
        if str(form.cleaned_data['request_key'])!=request.session[session_key]: form.add_error(None,'A sessão de compra foi atualizada. Reabra o evento.')
        else:
            try:
                order=create_order({**form.cleaned_data,'event_id':event.pk},fingerprint(request))
                return redirect('order',token=order.access_token)
            except ValidationError as exc: form.add_error(None,exc)
    return render(request,'core/checkout.html',{'event':event,'form':form})

@never_cache
def order_detail(request,token):
    order=get_object_or_404(Order.objects.select_related('event'),access_token=token)
    form=ReceiptForm(request.POST or None,request.FILES or None) if order.payment_provider!='pagarme' else None
    if request.method=='POST':
        if order.payment_provider=='pagarme':
            return JsonResponse({'detail':'Pedidos Pagar.me são confirmados automaticamente.'},status=405)
        if form.is_valid():
            try:
                report_receipt(order.pk,form.cleaned_data['receipt']); messages.success(request,'Comprovante enviado. Aguarde a conferência da equipe.'); return redirect('order',token=token)
            except ValidationError as exc: form.add_error(None,exc)
    return render(request,'core/order.html',{
        'order':order,
        'form':form,
        'pix':pix_payload(order) if order.status=='pending' and not order.expired else '',
        'automatic_payment':order.payment_provider=='pagarme',
    })

@never_cache
def pix_qr(request,token):
    import qrcode
    order=get_object_or_404(Order,access_token=token,status='pending')
    if order.expired: raise Http404
    output=BytesIO(); qrcode.make(pix_payload(order)).save(output,format='PNG')
    return HttpResponse(output.getvalue(),content_type='image/png')

@csrf_exempt
@require_POST
def pagarme_webhook(request):
    if not getattr(settings,'PAGARME_CONFIGURED',False):
        return JsonResponse({'ok':False},status=503)
    try:
        payload=json.loads(request.body.decode('utf-8'))
    except (ValueError,UnicodeDecodeError):
        return JsonResponse({'ok':False},status=400)
    event_type=str(payload.get('type') or '')
    data=payload.get('data') or {}
    order=None
    if event_type.startswith('order.') and data.get('id'):
        order=Order.objects.filter(payment_provider='pagarme',provider_order_id=str(data.get('id'))).first()
    elif event_type.startswith('charge.') and data.get('id'):
        order=Order.objects.filter(payment_provider='pagarme',provider_charge_id=str(data.get('id'))).first()
    if order is None:
        return JsonResponse({'ok':True})
    if event_type in ['order.paid','order.payment_failed','order.canceled','charge.paid','charge.payment_failed','charge.refunded','charge.pending']:
        try:
            sync_pagarme_charge(order.pk)
        except ValidationError:
            return JsonResponse({'ok':False},status=502)
    return JsonResponse({'ok':True})

@never_cache
def official_ticket(request,token):
    order=get_object_or_404(Order,access_token=token,status='paid')
    if not order.official_ticket: raise Http404
    return FileResponse(order.official_ticket.open('rb'),as_attachment=True,filename=f'ingresso-{order.code}.pdf',content_type='application/pdf')

@never_cache
def ticket_file(request,token,pk):
    ticket=get_object_or_404(OrderTicket.objects.select_related('order'),pk=pk,order__access_token=token,order__status='paid')
    return FileResponse(ticket.file.open('rb'),as_attachment=True,filename=f'ingresso-{ticket.order.code}-{ticket.pk}.pdf',content_type='application/pdf')

@operator_required
def dashboard(request):
    paid=Order.objects.filter(status='paid')
    gross=Order.objects.filter(paid_at__isnull=False).aggregate(n=Sum('total'))['n'] or Decimal('0')
    refunds=Order.objects.filter(status='refunded').aggregate(n=Sum('total'))['n'] or Decimal('0')
    fees=Order.objects.filter(paid_at__isnull=False).aggregate(n=Sum('fee'))['n'] or Decimal('0')
    outgoing=Expense.objects.aggregate(n=Sum('amount'))['n'] or Decimal('0')
    pending=Order.objects.filter(Q(status='review')|Q(status='pending',expires_at__gt=timezone.now())).aggregate(n=Sum('total'))['n'] or Decimal('0')
    sold=paid.aggregate(n=Sum('quantity'))['n'] or 0
    paid_orders=paid.count()
    paid_revenue=paid.aggregate(n=Sum('total'))['n'] or Decimal('0')
    avg_ticket=(paid_revenue/paid_orders) if paid_orders else Decimal('0')
    now=timezone.localdate()
    months=[]
    for offset in range(5,-1,-1):
        month_index=now.year*12+now.month-1-offset
        y,m=divmod(month_index,12); m+=1
        total=paid.filter(paid_at__year=y,paid_at__month=m).aggregate(n=Sum('total'))['n'] or Decimal('0')
        months.append({'label':['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'][m-1],'value':total})
    maximum=max([x['value'] for x in months] or [0])
    for item in months: item['height']=round(item['value']/maximum*100) if maximum else 0
    current_month=paid.filter(paid_at__year=now.year,paid_at__month=now.month).aggregate(n=Sum('total'))['n'] or Decimal('0')
    prev_index=now.year*12+now.month-2
    py,pm0=divmod(prev_index,12); pm=pm0+1
    previous_month=paid.filter(paid_at__year=py,paid_at__month=pm).aggregate(n=Sum('total'))['n'] or Decimal('0')
    monthly_change=None
    monthly_change_label='Sem base de comparação no mês anterior'
    if previous_month:
        monthly_change=round(float((current_month-previous_month)/previous_month*100),1)
        sign='+' if monthly_change>=0 else ''
        monthly_change_label=f'{sign}{monthly_change}% comparado ao mês anterior'
    upcoming_qs=Event.objects.filter(status='published',starts_at__gte=timezone.now()).order_by('starts_at')
    capacity_total=sum(event.capacity for event in upcoming_qs)
    upcoming_sold=sum(event.sold for event in upcoming_qs)
    occupancy_percent=round(upcoming_sold/capacity_total*100) if capacity_total else 0
    top_events=[]
    for event in Event.objects.filter(orders__status='paid').distinct():
        revenue=event.orders.filter(status='paid').aggregate(n=Sum('total'))['n'] or Decimal('0')
        qty=event.orders.filter(status='paid').aggregate(n=Sum('quantity'))['n'] or 0
        top_events.append({'event':event,'revenue':revenue,'sold':qty})
    top_events=sorted(top_events,key=lambda item:item['revenue'],reverse=True)[:5]
    return render(request,'panel/dashboard.html',{
        'active':'dashboard','gross':gross,'refunds':refunds,'fees':fees,'outgoing':outgoing,'balance':gross-refunds-fees-outgoing,
        'sold':sold,'pending':pending,'months':months,'has_sales':bool(maximum),'recent_orders':Order.objects.select_related('event')[:6],
        'upcoming':Event.objects.filter(starts_at__gte=timezone.now()).order_by('starts_at')[:4],
        'review_count':Order.objects.filter(status='review').count(),'published_count':upcoming_qs.count(),
        'avg_ticket':avg_ticket,'occupancy_percent':occupancy_percent,'top_events':top_events,
        'current_month':current_month,'previous_month':previous_month,'monthly_change':monthly_change,'monthly_change_label':monthly_change_label,
    })

@operator_required
def production_status(request):
    database_engine=settings.DATABASES['default']['ENGINE']
    checks=[
        {'label':'Modo de produção (DEBUG desligado)','ok':not settings.DEBUG,'detail':'Evita páginas de erro com detalhes internos.'},
        {'label':'Banco PostgreSQL','ok':not database_engine.endswith('sqlite3'),'detail':'Necessário para estoque e pedidos concorrentes.'},
        {'label':'Uploads persistentes no S3','ok':getattr(settings,'S3_CONFIGURED',False),'detail':'Preserva fotos, comprovantes e ingressos entre deploys.'},
        {'label':'SECRET_KEY persistente','ok':getattr(settings,'SECRET_KEY_PERSISTENT',False),'detail':'Mantém sessões e tokens estáveis entre deploys.'},
        {'label':'E-mails transacionais','ok':getattr(settings,'EMAIL_NOTIFICATIONS_ENABLED',False),'detail':'Reserva, pagamento e ingresso podem gerar avisos automáticos.'},
        {'label':'WhatsApp transacional','ok':getattr(settings,'WHATSAPP_NOTIFICATIONS_ENABLED',False),'detail':'Ativa avisos pelo canal oficial quando URL e token forem configurados.'},
        {'label':'Pagar.me automático','ok':getattr(settings,'PAGARME_CONFIGURED',False),'detail':'Gera Pix pela API e confirma o pagamento por webhook após validação no gateway.'},
        {'label':'Domínio próprio','ok':'onrender.com' not in getattr(settings,'SITE_URL',''),'detail':'Opcional durante testes; recomendado para operação comercial.'},
    ]
    return render(request,'panel/production.html',{
        'active':'production','checks':checks,'db_expires':getattr(settings,'PRODUCTION_DB_EXPIRES_AT',''),
        'site_url':getattr(settings,'SITE_URL',''),'payment_provider':getattr(settings,'PAYMENT_PROVIDER','manual'),'pagarme_webhook_url':f"{getattr(settings,'SITE_URL','')}/webhooks/pagarme/",
    })

@operator_required
def backup_export(request):
    events=[]
    for event in Event.objects.all():
        events.append({
            'id':str(event.pk),'title':event.title,'category':event.category,'starts_at':event.starts_at.isoformat(),
            'doors_at':event.doors_at.isoformat() if event.doors_at else None,'price':str(event.price),'capacity':event.capacity,
            'status':event.status,'location':event.location,'includes':event.includes,'food_info':event.food_info,
            'drinks_info':event.drinks_info,'parking_info':event.parking_info,'age_rules':event.age_rules,
        })
    orders=[]
    for order in Order.objects.select_related('event').all():
        orders.append({
            'id':str(order.pk),'code':order.code,'event_id':str(order.event_id),'customer_name':order.customer_name,
            'email':order.email,'phone':order.phone,'quantity':order.quantity,'unit_price':str(order.unit_price),
            'total':str(order.total),'fee':str(order.fee),'status':order.status,'created_at':order.created_at.isoformat(),
            'paid_at':order.paid_at.isoformat() if order.paid_at else None,
        })
    expenses=[{'id':x.pk,'description':x.description,'amount':str(x.amount),'kind':x.kind,'date':x.date.isoformat()} for x in Expense.objects.all()]
    cfg=SiteSettings.objects.filter(pk=1).first()
    data={
        'generated_at':timezone.now().isoformat(),'version':1,
        'site':{'texts':cfg.texts if cfg else {},'instagram':cfg.instagram if cfg else '','whatsapp':cfg.whatsapp if cfg else '','contact_email':cfg.contact_email if cfg else '','sales_enabled':cfg.sales_enabled if cfg else False},
        'events':events,'orders':orders,'expenses':expenses,
    }
    response=HttpResponse(json.dumps(data,ensure_ascii=False,indent=2),content_type='application/json; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="resenha-backup-{timezone.localdate().isoformat()}.json"'
    log(request.user,'Backup administrativo exportado')
    return response

@operator_required
def panel_events(request):
    events=Event.objects.all()
    search=request.GET.get('q','').strip()
    if search: events=events.filter(title__icontains=search)
    status=request.GET.get('status','')
    if status in dict(Event.STATUSES): events=events.filter(status=status)
    return render(request,'panel/events.html',{'active':'events','events':events,'search':search,'status':status})

@operator_required
def event_edit(request,pk=None):
    event=get_object_or_404(Event,pk=pk) if pk else None
    form=EventForm(request.POST or None,request.FILES or None,instance=event)
    if request.method=='POST' and form.is_valid():
        try:
            photos=request.FILES.getlist('gallery')
            if len(photos)+(event.photos.count() if event else 0)>12: raise ValidationError('Use até 12 fotos na galeria.')
            clean_photos=[clean_image(photo) for photo in photos]
            with transaction.atomic():
                if event:
                    locked=Event.objects.select_for_update().get(pk=event.pk)
                    if form.cleaned_data['capacity']<occupied(locked): raise ValidationError('A quantidade total não pode ficar abaixo dos ingressos confirmados e reservados.')
                saved=form.save()
                for photo in clean_photos: EventPhoto.objects.create(event=saved,image=photo)
                log(request.user,'Evento salvo',saved.pk)
            messages.success(request,'Evento salvo. A data já está na Agenda.'); return redirect('panel_events')
        except ValidationError as exc: form.add_error(None,exc)
    return render(request,'panel/event_form.html',{'active':'events','form':form,'event':event})

@operator_required
@require_POST
def event_delete(request,pk):
    with transaction.atomic():
        event=get_object_or_404(Event.objects.select_for_update(),pk=pk)
        if event.orders.exists():
            event.status='closed'; event.save(update_fields=['status']); messages.info(request,'O evento foi encerrado. Os pedidos foram preservados.')
        else: event.delete(); messages.success(request,'Evento excluído.')
        log(request.user,'Evento excluído ou encerrado',pk)
    return redirect('panel_events')

@operator_required
@require_POST
def photo_delete(request,pk):
    photo=get_object_or_404(EventPhoto,pk=pk); event_id=photo.event_id
    photo.delete(); log(request.user,'Foto removida',pk)
    return redirect('event_edit',pk=event_id)

@operator_required
def agenda(request):
    today=timezone.localdate()
    try:
        year=int(request.GET.get('ano',today.year)); month=int(request.GET.get('mes',today.month))
        if not 2020<=year<=2100 or not 1<=month<=12: raise ValueError
    except ValueError: year,month=today.year,today.month
    first=date(year,month,1)
    next_month=date(year+1,1,1) if month==12 else date(year,month+1,1)
    prev=first-timedelta(days=1)
    events=list(Event.objects.filter(starts_at__date__gte=first,starts_at__date__lt=next_month))
    event_days={}
    for e in events: event_days.setdefault(timezone.localdate(e.starts_at),[]).append(e)
    weeks=[]
    for week in calendar.Calendar(firstweekday=6).monthdatescalendar(year,month):
        weeks.append([{'date':day,'current':day.month==month,'today':day==today,'events':event_days.get(day,[])} for day in week])
    month_name=['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'][month-1]
    return render(request,'panel/agenda.html',{'active':'agenda','weeks':weeks,'month_name':month_name,'year':year,'previous':prev,'next':next_month,'events':events,'today':today})

@operator_required
def panel_orders(request):
    orders=Order.objects.select_related('event')
    search=request.GET.get('q','').strip(); status=request.GET.get('status',''); event=request.GET.get('evento','')
    if search: orders=orders.filter(Q(customer_name__icontains=search)|Q(email__icontains=search)|Q(phone__icontains=search))
    if status in dict(Order.STATUSES): orders=orders.filter(status=status)
    if event:
        try: orders=orders.filter(event_id=uuid.UUID(event))
        except ValueError: pass
    page=Paginator(orders,25).get_page(request.GET.get('pagina',1))
    return render(request,'panel/orders.html',{'active':'orders','page_obj':page,'search':search,'status':status,'selected_event':event,'all_events':Event.objects.all(),'statuses':Order.STATUSES})

@operator_required
def panel_order(request,pk):
    order=get_object_or_404(Order.objects.select_related('event'),pk=pk)
    ticket_form=TicketForm(request.POST or None,request.FILES or None)
    if request.method=='POST' and request.POST.get('action')=='ticket':
        if order.status!='paid':
            messages.error(request,'Confirme o pagamento antes de anexar o ingresso oficial.')
        elif order.tickets.count() + (1 if order.official_ticket else 0) >= order.quantity:
            messages.error(request,'Este pedido já possui a quantidade de ingressos correspondente à compra.')
        elif ticket_form.is_valid():
            number=order.tickets.count() + (2 if order.official_ticket else 1)
            ticket=OrderTicket.objects.create(
                order=order,
                file=ticket_form.cleaned_data['official_ticket'],
                label=ticket_form.cleaned_data.get('label') or f'Ingresso {number}',
            )
            log(request.user,'Ingresso oficial anexado',ticket.pk)
            transaction.on_commit(lambda: notify_order(order.pk,'ticket'))
            messages.success(request,'Ingresso disponibilizado na página privada do pedido.')
            return redirect('panel_order',pk=pk)
    elif request.method=='POST':
        try:
            fee=Decimal(request.POST.get('fee','0').replace(',','.'))
            if not fee.is_finite(): raise InvalidOperation
            change_order(order.pk,request.POST.get('status'),request.user,fee=fee)
            messages.success(request,'Pedido atualizado.'); return redirect('panel_order',pk=pk)
        except (ValidationError,InvalidOperation) as exc: messages.error(request,' '.join(exc.messages) if isinstance(exc,ValidationError) else 'Informe uma taxa válida.')
    return render(request,'panel/order_detail.html',{'active':'orders','order':order,'ticket_form':ticket_form})

@operator_required
@require_POST
def ticket_delete(request,pk):
    ticket=get_object_or_404(OrderTicket.objects.select_related('order'),pk=pk)
    order_pk=ticket.order_id
    ticket.file.delete(save=False)
    log(request.user,'Ingresso oficial removido',ticket.pk)
    ticket.delete()
    messages.success(request,'Ingresso removido do pedido.')
    return redirect('panel_order',pk=order_pk)

@operator_required
def receipt_file(request,pk):
    order=get_object_or_404(Order,pk=pk)
    if not order.receipt: raise Http404
    return FileResponse(order.receipt.open('rb'),content_type='image/webp')

@operator_required
def finance(request):
    form=ExpenseForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        expense=form.save(commit=False); expense.created_by=request.user; expense.save(); log(request.user,'Saída financeira registrada',expense.pk); messages.success(request,'Lançamento registrado.'); return redirect('finance')
    gross=Order.objects.filter(paid_at__isnull=False).aggregate(n=Sum('total'))['n'] or Decimal('0')
    refunds=Order.objects.filter(status='refunded').aggregate(n=Sum('total'))['n'] or Decimal('0')
    fees=Order.objects.filter(paid_at__isnull=False).aggregate(n=Sum('fee'))['n'] or Decimal('0')
    expenses=Expense.objects.all(); outgoing=expenses.aggregate(n=Sum('amount'))['n'] or Decimal('0')
    return render(request,'panel/finance.html',{'active':'finance','form':form,'expenses':expenses,'gross':gross,'refunds':refunds,'fees':fees,'outgoing':outgoing,'balance':gross-refunds-fees-outgoing})

@operator_required
@require_POST
def expense_delete(request,pk):
    expense=get_object_or_404(Expense,pk=pk); log(request.user,f'Lançamento removido: {expense.description} ({expense.amount})',pk); expense.delete(); messages.success(request,'Lançamento removido.'); return redirect('finance')

@operator_required
def banners(request):
    return render(request,'panel/banners.html',{'active':'banners','banners':Banner.objects.all()})
@operator_required
def banner_edit(request,pk=None):
    banner=get_object_or_404(Banner,pk=pk) if pk else None
    form=BannerForm(request.POST or None,request.FILES or None,instance=banner)
    if request.method=='POST' and form.is_valid():
        saved=form.save(); log(request.user,'Banner salvo',saved.pk); messages.success(request,'Banner salvo.'); return redirect('banners')
    return render(request,'panel/generic_form.html',{'active':'banners','title':'Editar banner' if banner else 'Novo banner','form':form,'back':'banners','subtitle':'Os banners ativos aparecem no carrossel da página inicial.'})
@operator_required
@require_POST
def banner_delete(request,pk):
    get_object_or_404(Banner,pk=pk).delete(); log(request.user,'Banner removido',pk); messages.success(request,'Banner removido.'); return redirect('banners')

@operator_required
def content_edit(request):
    cfg,_=SiteSettings.objects.get_or_create(pk=1)
    group=request.GET.get('grupo',next(iter(CONTENT)))
    if group not in CONTENT: group=next(iter(CONTENT))
    form=ContentForm(request.POST or None,group=group,values=cfg.texts)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            cfg=SiteSettings.objects.select_for_update().get(pk=1); cfg.texts={**cfg.texts,**form.cleaned_data}; cfg.save(update_fields=['texts','updated_at']); log(request.user,f'Textos atualizados: {group}')
        messages.success(request,'Textos atualizados no site.'); return redirect(request.path+'?grupo='+__import__('urllib.parse',fromlist=['quote']).quote(group))
    return render(request,'panel/content.html',{'active':'content','groups':CONTENT,'group':group,'form':form})

@operator_required
def media_edit(request):
    cfg,_=SiteSettings.objects.get_or_create(pk=1)
    form=MediaForm(request.POST or None,request.FILES or None,instance=cfg)
    if request.method=='POST' and form.is_valid(): form.save(); log(request.user,'Imagens do site atualizadas'); messages.success(request,'Imagens atualizadas.'); return redirect('media_edit')
    return render(request,'panel/media.html',{'active':'media','form':form})

@operator_required
def settings_edit(request):
    cfg,_=SiteSettings.objects.get_or_create(pk=1)
    form=SettingsForm(request.POST or None,instance=cfg)
    if request.method=='POST' and form.is_valid(): form.save(); log(request.user,'Configurações atualizadas'); messages.success(request,'Configurações salvas.'); return redirect('settings_edit')
    return render(request,'panel/settings.html',{'active':'settings','form':form})

@operator_required
def export_orders(request):
    response=HttpResponse(content_type='text/csv; charset=utf-8-sig'); response['Content-Disposition']='attachment; filename="pedidos-resenha.csv"'; response.write('\ufeff')
    writer=csv.writer(response,delimiter=';'); writer.writerow(['Pedido','Evento','Cliente','E-mail','Telefone','Quantidade','Preço unitário','Total','Taxa','Status','Criado em'])
    def safe(value):
        s=str(value)
        return "'"+s if s[:1] in '=+-@\t\r\n' else s
    for o in Order.objects.select_related('event').iterator(): writer.writerow([safe(x) for x in [o.code,o.event.title,o.customer_name,o.email,o.phone,o.quantity,o.unit_price,o.total,o.fee,o.display_status,timezone.localtime(o.created_at).isoformat()]])
    log(request.user,'Relatório de pedidos exportado')
    return response
