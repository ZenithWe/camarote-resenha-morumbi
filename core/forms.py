import re, uuid, warnings
from io import BytesIO
from PIL import Image, ImageOps
from django import forms
from django.core.files.base import ContentFile
from django.utils import timezone
from .models import Event, Banner, SiteSettings, Expense
from .content import CONTENT, DEFAULT_TEXTS, FIELD_LABELS

Image.MAX_IMAGE_PIXELS=20_000_000

def clean_image(upload):
    if not upload or not hasattr(upload,'read'): return upload
    if upload.size>8*1024*1024: raise forms.ValidationError('Use uma imagem de até 8 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            upload.seek(0)
            image=Image.open(upload)
            if image.format not in ['JPEG','PNG','WEBP']: raise ValueError('Formato não permitido')
            image.load()
            if image.width*image.height>20_000_000: raise ValueError('Imagem muito grande')
            image=ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((2560,2560))
            output=BytesIO(); image.save(output,'WEBP',quality=86)
            return ContentFile(output.getvalue(),name=uuid.uuid4().hex+'.webp')
    except Exception as exc:
        raise forms.ValidationError('Envie uma imagem JPG, PNG ou WebP válida, de até 20 megapixels.') from exc

def secure_link(value):
    if value.startswith('/') and not value.startswith('//') and '\\' not in value: return value
    if value.startswith('#'): return value
    if value.startswith('https://'):
        forms.URLField().clean(value); return value
    raise forms.ValidationError('Use um endereço https:// ou um caminho do site, como /#eventos.')

class EventForm(forms.ModelForm):
    event_date=forms.DateField(label='Dia do evento',widget=forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d'),input_formats=['%Y-%m-%d'])
    event_time=forms.TimeField(label='Horário do evento',widget=forms.TimeInput(attrs={'type':'time'},format='%H:%M'),input_formats=['%H:%M'])
    class Meta:
        model=Event
        fields=['title','description','category','price','capacity','max_per_order','ticket_source','ticket_source_notes','doors_at','location','includes','food_info','drinks_info','parking_info','age_rules','cover','status','featured']
        widgets={'description':forms.Textarea(attrs={'rows':5}),'includes':forms.Textarea(attrs={'rows':4}),'food_info':forms.Textarea(attrs={'rows':2}),'drinks_info':forms.Textarea(attrs={'rows':2}),'parking_info':forms.Textarea(attrs={'rows':2}),'doors_at':forms.TimeInput(attrs={'type':'time'},format='%H:%M'),'price':forms.NumberInput(attrs={'step':'0.01','min':'1'}),'ticket_source_notes':forms.Textarea(attrs={'rows':2}),'cover':forms.ClearableFileInput(attrs={'accept':'image/jpeg,image/png,image/webp'})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['cover'].help_text='JPG, PNG ou WebP, até 8 MB. Formato horizontal recomendado.'
        if self.instance and self.instance.pk and self.instance.starts_at:
            dt=timezone.localtime(self.instance.starts_at)
            self.fields['event_date'].initial=dt.date()
            self.fields['event_time'].initial=dt.strftime('%H:%M')
    def clean_cover(self): return clean_image(self.cleaned_data.get('cover'))
    def clean(self):
        cleaned=super().clean()
        if cleaned.get('event_date') and cleaned.get('event_time'):
            from datetime import datetime
            self.instance.starts_at=timezone.make_aware(datetime.combine(cleaned['event_date'],cleaned['event_time']))
            if cleaned.get('status')=='published' and self.instance.starts_at<=timezone.now(): self.add_error('event_date','Para publicar, selecione uma data futura.')
        return cleaned

class BannerForm(forms.ModelForm):
    class Meta:
        model=Banner
        fields=['title','subtitle','eyebrow','image','button_text','link','active','position']
        widgets={'image':forms.ClearableFileInput(attrs={'accept':'image/jpeg,image/png,image/webp'})}
    def clean_image(self): return clean_image(self.cleaned_data.get('image'))
    def clean_link(self): return secure_link(self.cleaned_data['link'])

class SettingsForm(forms.ModelForm):
    class Meta:
        model=SiteSettings
        fields=['instagram','whatsapp','contact_email','pix_key','pix_name','pix_city','sales_enabled']
        labels={'instagram':'Instagram','whatsapp':'WhatsApp (país + DDD + número)','contact_email':'E-mail de contato','pix_key':'Chave Pix','pix_name':'Nome do recebedor','pix_city':'Cidade do recebedor','sales_enabled':'Ativar vendas por Pix'}
        help_texts={'whatsapp':'Opcional. Ex.: 5511999999999.','pix_key':'Cadastre a chave Pix da conta que receberá os pagamentos.','pix_name':'Nome do titular da conta, como aparece no banco.','sales_enabled':'A confirmação dos pagamentos é manual no painel.'}
    def clean_whatsapp(self):
        val=re.sub(r'\D','',self.cleaned_data['whatsapp'])
        if val and not re.fullmatch(r'\d{10,15}',val): raise forms.ValidationError('Informe um telefone com país e DDD.')
        return val
    def clean(self):
        cleaned=super().clean()
        if cleaned.get('sales_enabled') and not all(cleaned.get(x) for x in ['pix_key','pix_name','pix_city']): raise forms.ValidationError('Preencha a chave Pix, o titular e a cidade antes de ativar as vendas.')
        return cleaned

class MediaForm(forms.ModelForm):
    class Meta:
        model=SiteSettings
        fields=['logo','hero_image','football_image','concert_image','experience_image']
        labels={'logo':'Logo','hero_image':'Imagem do banner principal','football_image':'Imagem da seção Futebol','concert_image':'Imagem da seção Shows','experience_image':'Imagem da seção O camarote'}
    def clean(self):
        cleaned=super().clean()
        for key in self.fields:
            if cleaned.get(key) and key in self.files:
                try: cleaned[key]=clean_image(cleaned[key])
                except forms.ValidationError as e: self.add_error(key,e)
        return cleaned

class ContentForm(forms.Form):
    def __init__(self,*args,group=None,values=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.group=group or next(iter(CONTENT))
        for key,default in CONTENT[self.group].items():
            self.fields[key]=forms.CharField(label=FIELD_LABELS.get(key,key.replace('_',' ').capitalize()),required=True,max_length=6000,initial=(values or {}).get(key,default),widget=forms.Textarea(attrs={'rows':3 if len(default)>90 else 2}))

class CheckoutForm(forms.Form):
    customer_name=forms.CharField(label='Nome completo',min_length=4,max_length=120,widget=forms.TextInput(attrs={'autocomplete':'name'}))
    email=forms.EmailField(label='E-mail',widget=forms.EmailInput(attrs={'autocomplete':'email'}))
    phone=forms.CharField(label='Celular com DDD',max_length=25,widget=forms.TextInput(attrs={'autocomplete':'tel','inputmode':'tel'}))
    quantity=forms.IntegerField(label='Quantidade de ingressos',min_value=1,max_value=20,initial=1)
    terms=forms.BooleanField(label='Li as informações da compra e as regras do evento.')
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    website=forms.CharField(required=False,widget=forms.TextInput(attrs={'tabindex':'-1','autocomplete':'off'}))
    def clean_phone(self):
        val=re.sub(r'\D','',self.cleaned_data['phone'])
        if len(val) in [12,13] and val.startswith('55'): val=val[2:]
        if not re.fullmatch(r'[1-9]\d\d{8,9}',val) or len(set(val))<=2: raise forms.ValidationError('Informe um celular válido com DDD.')
        return '55'+val
    def clean_website(self):
        if self.cleaned_data['website']: raise forms.ValidationError('Não foi possível enviar o pedido.')
        return ''

class ReceiptForm(forms.Form):
    receipt=forms.ImageField(label='Comprovante de pagamento',widget=forms.FileInput(attrs={'accept':'image/jpeg,image/png,image/webp'}))
    def clean_receipt(self): return clean_image(self.cleaned_data['receipt'])

class TicketForm(forms.Form):
    official_ticket=forms.FileField(label='Adicionar ingresso oficial em PDF',widget=forms.FileInput(attrs={'accept':'application/pdf'}))
    label=forms.CharField(label='Identificação',required=False,max_length=80,help_text='Opcional. Ex.: Ingresso 1, Cadeira A12 ou titular.')
    def clean_official_ticket(self):
        f=self.cleaned_data['official_ticket']
        if f.size>10*1024*1024: raise forms.ValidationError('O PDF deve ter até 10 MB.')
        signature=f.read(5); f.seek(0)
        if signature!=b'%PDF-': raise forms.ValidationError('Envie um arquivo PDF válido.')
        return f

class ExpenseForm(forms.ModelForm):
    class Meta:
        model=Expense
        fields=['description','amount','kind','date']
        widgets={'amount':forms.NumberInput(attrs={'min':'0.01','step':'0.01'}),'date':forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d')}
