import secrets, uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.core.files.storage import storages
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

def private_storage(): return storages['private']
def upload_path(instance,filename): return f'images/{uuid.uuid4().hex}.webp'
def private_image_path(instance,filename): return f'receipts/{uuid.uuid4().hex}.webp'
def ticket_path(instance,filename): return f'tickets/{uuid.uuid4().hex}.pdf'
def order_token(): return secrets.token_urlsafe(32)

class SiteSettings(models.Model):
    id=models.PositiveSmallIntegerField(primary_key=True,default=1,editable=False)
    texts=models.JSONField(default=dict,blank=True)
    instagram=models.URLField(default='https://www.instagram.com/resenhamorumbi/')
    whatsapp=models.CharField(max_length=15,blank=True)
    contact_email=models.EmailField(blank=True)
    logo=models.ImageField(upload_to=upload_path,blank=True)
    hero_image=models.ImageField(upload_to=upload_path,blank=True)
    football_image=models.ImageField(upload_to=upload_path,blank=True)
    concert_image=models.ImageField(upload_to=upload_path,blank=True)
    experience_image=models.ImageField(upload_to=upload_path,blank=True)
    pix_key=models.CharField(max_length=77,blank=True)
    pix_name=models.CharField(max_length=25,blank=True)
    pix_city=models.CharField(max_length=15,default='SAO PAULO')
    sales_enabled=models.BooleanField(default=False)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: verbose_name='configuração do site'
    def save(self,*args,**kwargs): self.pk=1; super().save(*args,**kwargs)
    def __str__(self): return 'Camarote Resenha Morumbi'

class Event(models.Model):
    CATEGORIES=[('football','Futebol'),('concert','Show')]
    STATUSES=[('draft','Rascunho'),('published','Publicado'),('closed','Encerrado')]
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    title=models.CharField('nome do evento',max_length=160)
    description=models.TextField('descrição',max_length=10000)
    category=models.CharField('categoria',choices=CATEGORIES,max_length=16)
    starts_at=models.DateTimeField('data e horário')
    doors_at=models.TimeField('abertura do camarote',blank=True,null=True)
    price=models.DecimalField('preço por ingresso',max_digits=10,decimal_places=2,validators=[MinValueValidator(Decimal('1.00'))])
    capacity=models.PositiveIntegerField('quantidade de ingressos',validators=[MinValueValidator(1),MaxValueValidator(100000)])
    max_per_order=models.PositiveSmallIntegerField('limite por pedido',default=8,validators=[MinValueValidator(1),MaxValueValidator(20)])
    location=models.CharField('local',max_length=240,default='MorumBIS • São Paulo, SP')
    includes=models.TextField('o que está incluído (um item por linha)',blank=True,max_length=2000)
    age_rules=models.CharField('classificação etária e regras',max_length=600,blank=True)
    cover=models.ImageField('foto de capa',upload_to=upload_path,blank=True)
    status=models.CharField('situação',choices=STATUSES,max_length=16,default='draft')
    featured=models.BooleanField('evento em destaque',default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['starts_at']
        indexes=[models.Index(fields=['status','starts_at'])]
        constraints=[models.CheckConstraint(condition=Q(capacity__gte=1),name='event_capacity_positive'),models.CheckConstraint(condition=Q(price__gte=1),name='event_price_positive')]
    @property
    def sold(self): return self.orders.filter(status='paid').aggregate(n=Sum('quantity'))['n'] or 0
    @property
    def occupied(self): return self.orders.filter(Q(status__in=['paid','review'])|Q(status='pending',expires_at__gt=timezone.now())).aggregate(n=Sum('quantity'))['n'] or 0
    @property
    def available(self): return max(0,self.capacity-self.occupied)
    @property
    def is_past(self): return self.starts_at<=timezone.now()
    def __str__(self): return self.title

class EventPhoto(models.Model):
    event=models.ForeignKey(Event,on_delete=models.CASCADE,related_name='photos')
    image=models.ImageField(upload_to=upload_path)
    caption=models.CharField(max_length=240,blank=True)

class Banner(models.Model):
    title=models.CharField('título',max_length=140)
    subtitle=models.CharField('texto de apoio',max_length=300,blank=True)
    eyebrow=models.CharField('chamada',max_length=80,default='CAMAROTE RESENHA MORUMBI')
    image=models.ImageField('imagem do banner',upload_to=upload_path)
    button_text=models.CharField('texto do botão',max_length=60,default='Ver eventos')
    link=models.CharField('link do botão',max_length=500,default='/#eventos')
    active=models.BooleanField('exibir na página inicial',default=True)
    position=models.PositiveSmallIntegerField('ordem',default=0)
    class Meta: ordering=['position','id']
    def __str__(self): return self.title

class Order(models.Model):
    STATUSES=[('pending','Aguardando pagamento'),('review','Em análise'),('paid','Confirmado'),('cancelled','Cancelado'),('refunded','Reembolsado')]
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    access_token=models.CharField(max_length=64,default=order_token,unique=True,editable=False)
    event=models.ForeignKey(Event,on_delete=models.PROTECT,related_name='orders')
    customer_name=models.CharField(max_length=120)
    email=models.EmailField()
    phone=models.CharField(max_length=15)
    quantity=models.PositiveSmallIntegerField(validators=[MinValueValidator(1),MaxValueValidator(20)])
    unit_price=models.DecimalField(max_digits=10,decimal_places=2)
    total=models.DecimalField(max_digits=12,decimal_places=2)
    status=models.CharField(max_length=16,choices=STATUSES,default='pending')
    expires_at=models.DateTimeField()
    created_at=models.DateTimeField(auto_now_add=True)
    paid_at=models.DateTimeField(null=True,blank=True)
    reported_at=models.DateTimeField(null=True,blank=True)
    refunded_at=models.DateTimeField(null=True,blank=True)
    fee=models.DecimalField(max_digits=10,decimal_places=2,default=0,validators=[MinValueValidator(0)])
    receipt=models.ImageField(upload_to=private_image_path,storage=private_storage,blank=True)
    official_ticket=models.FileField(upload_to=ticket_path,storage=private_storage,blank=True)
    request_key=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    ip_hash=models.CharField(max_length=64,blank=True)
    pix_snapshot=models.JSONField(default=dict)
    class Meta:
        ordering=['-created_at']
        indexes=[models.Index(fields=['event','status','expires_at']),models.Index(fields=['ip_hash','created_at'])]
        constraints=[models.CheckConstraint(condition=Q(quantity__gte=1),name='order_quantity_positive')]
    @property
    def code(self): return str(self.id).split('-')[0].upper()
    @property
    def expired(self): return self.status=='pending' and self.expires_at<=timezone.now()
    @property
    def display_status(self): return 'Reserva expirada' if self.expired else self.get_status_display()
    def __str__(self): return f'{self.code} • {self.customer_name}'

class Expense(models.Model):
    TYPES=[('expense','Despesa'),('withdrawal','Retirada')]
    description=models.CharField('descrição',max_length=180)
    amount=models.DecimalField('valor',max_digits=12,decimal_places=2,validators=[MinValueValidator(Decimal('0.01'))])
    kind=models.CharField('tipo',max_length=16,choices=TYPES,default='expense')
    date=models.DateField('data',default=timezone.localdate)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-date','-id']

class AuditLog(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    action=models.CharField(max_length=180)
    object_id=models.CharField(max_length=80,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']
