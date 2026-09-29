import io, uuid, tempfile
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from core.models import SiteSettings, Event, Order, Expense, Banner
from core.services import create_order, change_order, report_receipt, pix_payload
from core.forms import EventForm, SettingsForm, BannerForm, clean_image
from core.content import DEFAULT_TEXTS

@override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'},'private':{'BACKEND':'django.core.files.storage.InMemoryStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}},AXES_ENABLED=False,SECURE_SSL_REDIRECT=False)
class CoreFlows(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser('owner','owner@example.test','An-example-only-password-2026!')
        self.cfg=SiteSettings.objects.create(pix_key='financeiro@example.test',pix_name='TESTE RESENHA',pix_city='SAO PAULO',sales_enabled=True)
        self.event=Event.objects.create(title='Evento de teste',description='Somente teste automatizado',category='football',starts_at=timezone.now()+timedelta(days=10),price=Decimal('150.00'),capacity=3,status='published')
    def order_data(self,**kw):
        return {'event_id':self.event.pk,'customer_name':'Pessoa de Teste','email':'cliente@example.test','phone':'5511999991234','quantity':1,'request_key':uuid.uuid4(),**kw}
    def create(self,**kw): return create_order(self.order_data(**kw),'ip-test')
    def image(self):
        image=Image.new('RGB',(20,20),'red'); out=io.BytesIO();image.save(out,format='PNG')
        return SimpleUploadedFile('example.png',out.getvalue(),content_type='image/png')
    def test_admin_routes_require_superuser(self):
        self.assertEqual(self.client.get('/painel/').status_code,302)
        user=get_user_model().objects.create_user('normal','normal@example.test','safe-test-password',is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/painel/').status_code,302)
        self.assertEqual(self.client.post(reverse('event_delete',args=[self.event.pk])).status_code,302)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())
    def test_csrf_prevents_forged_admin_writes(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(reverse('event_delete',args=[self.event.pk])).status_code,403)
    def test_idempotent_order_and_server_side_price(self):
        data=self.order_data(quantity=2,unit_price=Decimal('0.01'),total=Decimal('0.02'))
        a=create_order(data,'ip');b=create_order(data,'ip')
        self.assertEqual(a.pk,b.pk);self.assertEqual(Order.objects.count(),1)
        self.assertEqual(a.total,Decimal('300.00'));self.assertEqual(self.event.available,1)
    def test_stock_limit_and_cancel_release(self):
        order=self.create(quantity=3)
        with self.assertRaises(ValidationError): self.create()
        change_order(order.pk,'cancelled',self.admin)
        self.assertEqual(self.event.available,3)
    def test_expiration_and_late_confirmation_stock(self):
        first=self.create(quantity=3);Order.objects.filter(pk=first.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        second=self.create(quantity=3)
        with self.assertRaises(ValidationError): change_order(first.pk,'paid',self.admin)
        change_order(second.pk,'paid',self.admin)
        self.assertEqual(self.event.sold,3)
    def test_refund_releases_stock_and_is_idempotent(self):
        order=self.create(quantity=2);change_order(order.pk,'paid',self.admin,Decimal('3.00'))
        with self.assertRaises(ValidationError): change_order(order.pk,'paid',self.admin)
        change_order(order.pk,'refunded',self.admin)
        self.assertEqual(self.event.sold,0);self.assertEqual(self.event.available,3)
    def test_receipt_review_holds_inventory(self):
        order=self.create(quantity=3);report_receipt(order.pk,clean_image(self.image()))
        Order.objects.filter(pk=order.pk).update(expires_at=timezone.now()-timedelta(days=2))
        self.assertEqual(self.event.available,0)
        order.refresh_from_db();self.assertEqual(order.status,'review')
    def test_upload_is_reencoded_and_scripts_rejected(self):
        original=self.image();malicious=SimpleUploadedFile('x.png',original.read()+b'<script>alert(1)</script>',content_type='image/png')
        sanitized=clean_image(malicious)
        self.assertNotIn(b'<script>',sanitized.read())
        with self.assertRaises(ValidationError): clean_image(SimpleUploadedFile('x.svg',b'<svg onload="alert(1)"></svg>',content_type='image/svg+xml'))
    def test_private_files_not_exposed(self):
        order=self.create();report_receipt(order.pk,clean_image(self.image()))
        self.assertEqual(self.client.get(reverse('receipt_file',args=[order.pk])).status_code,302)
        self.assertEqual(self.client.get(reverse('official_ticket',args=[order.access_token])).status_code,404)
        self.assertEqual(self.client.get('/media/../private-media/test.webp').status_code,404)
    def test_pix_uses_order_snapshot(self):
        order=self.create();self.cfg.pix_key='new@example.test';self.cfg.save()
        payload=pix_payload(order)
        self.assertIn('financeiro@example.test',payload);self.assertIn('150.00',payload);self.assertNotIn('new@example.test',payload)
        self.assertEqual(payload[-8:-4],'6304')
    def test_financial_totals(self):
        one=self.create();change_order(one.pk,'paid',self.admin,Decimal('2.00'))
        two=self.create();change_order(two.pk,'paid',self.admin);change_order(two.pk,'refunded',self.admin)
        Expense.objects.create(description='Saída de teste',amount=Decimal('20.00'),created_by=self.admin)
        self.client.force_login(self.admin);response=self.client.get('/painel/')
        self.assertEqual(response.context['gross'],Decimal('300.00'))
        self.assertEqual(response.context['balance'],Decimal('128.00'));self.assertEqual(response.context['sold'],1)
    def test_dates_appear_in_calendar_and_event_form(self):
        self.client.force_login(self.admin);day=timezone.localdate(self.event.starts_at)
        response=self.client.get('/painel/agenda/',{'ano':day.year,'mes':day.month})
        self.assertContains(response,'Evento de teste')
        response=self.client.get(reverse('event_edit',args=[self.event.pk]))
        self.assertContains(response,'type="date"');self.assertContains(response,day.isoformat())
    def test_editing_capacity_cannot_invalidate_reservations(self):
        self.create(quantity=3);self.client.force_login(self.admin)
        dt=timezone.localtime(self.event.starts_at)
        data={'title':'Evento alterado','description':'Descrição','category':'football','price':'150.00','capacity':2,'max_per_order':8,'ticket_source':'ticketmaster','ticket_source_notes':'Lote oficial','location':'MorumBIS','status':'published','event_date':dt.date().isoformat(),'event_time':dt.strftime('%H:%M')}
        response=self.client.post(reverse('event_edit',args=[self.event.pk]),data)
        self.assertContains(response,'não pode ficar abaixo');self.event.refresh_from_db();self.assertEqual(self.event.capacity,3)
    def test_settings_require_pix_and_banner_urls_safe(self):
        form=SettingsForm({'instagram':self.cfg.instagram,'pix_key':'','pix_name':'','pix_city':'SAO PAULO','sales_enabled':True},instance=self.cfg)
        self.assertFalse(form.is_valid())
        from core.forms import secure_link
        with self.assertRaises(ValidationError): secure_link('javascript:alert(1)')
        with self.assertRaises(ValidationError): secure_link('//evil.example')
    def test_cms_content_is_escaped(self):
        self.cfg.texts={'hero_title':'<script>alert(1)</script>'};self.cfg.save()
        response=self.client.get('/')
        self.assertContains(response,'&lt;script&gt;');self.assertNotContains(response,'<script>alert(1)</script>')
    def test_customer_checkout_receipt_and_ticket_pages(self):
        response=self.client.get(reverse('checkout',args=[self.event.pk]));self.assertEqual(response.status_code,200)
        key=self.client.session[f'checkout_{self.event.pk}']
        data={'customer_name':'Pessoa Compradora','email':'buyer@example.test','phone':'11999991234','quantity':2,'terms':'on','request_key':key}
        response=self.client.post(reverse('checkout',args=[self.event.pk]),data);self.assertEqual(response.status_code,302)
        response=self.client.get(response.url);self.assertContains(response,'Pague com Pix')
        order=Order.objects.get();self.assertEqual(self.client.get(reverse('pix_qr',args=[order.access_token])).status_code,200)
        response=self.client.post(reverse('order',args=[order.access_token]),{'receipt':self.image()});self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'Comprovante recebido')
        self.client.get(reverse('checkout',args=[self.event.pk]))
        new_key=self.client.session[f'checkout_{self.event.pk}']
        self.assertNotEqual(key,new_key)
        data.update(request_key=new_key,quantity=1)
        self.assertEqual(self.client.post(reverse('checkout',args=[self.event.pk]),data).status_code,302)
        self.assertEqual(Order.objects.count(),2)
    def test_all_management_pages_render(self):
        self.client.force_login(self.admin)
        for url in ['/painel/','/painel/eventos/','/painel/eventos/novo/','/painel/agenda/','/painel/pedidos/','/painel/financeiro/','/painel/banners/','/painel/banners/novo/','/painel/conteudo/','/painel/imagens/','/painel/configuracoes/','/painel/senha/']:
            with self.subTest(url=url): self.assertEqual(self.client.get(url).status_code,200)
