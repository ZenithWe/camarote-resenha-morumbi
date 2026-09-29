import hashlib, hmac, uuid
from datetime import timedelta
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import SiteSettings, Event, Coupon, EventTicket, Order
from .services import create_order, assign_event_tickets, validate_mercadopago_webhook
from .forms import EventForm

@override_settings(PAYMENT_PROVIDER='manual')
class CommerceTests(TestCase):
    def setUp(self):
        SiteSettings.objects.create(pk=1,pix_key='teste@example.com',pix_name='RESENHA',pix_city='SAO PAULO',sales_enabled=True)
        self.event=Event.objects.create(
            title='Evento teste',description='Teste',category='football',
            starts_at=timezone.now()+timedelta(days=10),price=Decimal('100.00'),
            capacity=20,max_per_order=4,status='published'
        )

    def order_data(self,**extra):
        data={'event_id':self.event.pk,'customer_name':'Cliente Teste','email':'cliente@example.com','phone':'5511999999999','quantity':2,'request_key':uuid.uuid4(),'coupon_code':''}
        data.update(extra)
        return data

    def test_coupon_applies_to_total(self):
        Coupon.objects.create(code='DEZ',discount_type='percent',value=Decimal('10'),max_uses=5,active=True)
        order=create_order(self.order_data(coupon_code='DEZ'),'hash')
        self.assertEqual(order.discount_amount,Decimal('20.00'))
        self.assertEqual(order.total,Decimal('180.00'))

    def test_paid_order_receives_inventory(self):
        order=create_order(self.order_data(),'hash')
        order.status='paid'; order.paid_at=timezone.now(); order.save(update_fields=['status','paid_at'])
        for i in range(2):
            EventTicket.objects.create(event=self.event,label=f'Ingresso {i+1}',file=SimpleUploadedFile(f'i{i}.pdf',b'%PDF-1.4\n%%EOF',content_type='application/pdf'))
        assigned=assign_event_tickets(order.pk)
        self.assertEqual(assigned,2)
        self.assertEqual(order.assigned_tickets.count(),2)

class MercadoPagoSignatureTests(TestCase):
    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='segredo')
    def test_valid_signature(self):
        data_id='12345'; request_id='abc'; ts='1700000000'
        manifest=f'id:{data_id};request-id:{request_id};ts:{ts};'
        signature=hmac.new(b'segredo',manifest.encode(),hashlib.sha256).hexdigest()
        header=f'ts={ts},v1={signature}'
        self.assertTrue(validate_mercadopago_webhook(header,request_id,data_id))


@override_settings(PAYMENT_PROVIDER='mercadopago',MERCADOPAGO_ACCESS_TOKEN='',MERCADOPAGO_CONFIGURED=False)
class AdminTestModeFlowTests(TestCase):
    def setUp(self):
        SiteSettings.objects.create(pk=1,sales_enabled=False)
        self.event=Event.objects.create(
            title='[TESTE] Fluxo completo',description='Teste',category='football',
            starts_at=timezone.now()+timedelta(days=7),price=Decimal('50.00'),
            capacity=10,max_per_order=4,status='published'
        )
        self.admin=get_user_model().objects.create_superuser(username='admin-test',email='admin@example.com',password=None)
        self.client.force_login(self.admin,backend='django.contrib.auth.backends.ModelBackend')

    def test_admin_can_test_checkout_and_customer_login_without_external_credentials(self):
        response=self.client.post(reverse('toggle_test_mode'),{'enabled':'1'})
        self.assertEqual(response.status_code,302)
        response=self.client.get(reverse('checkout',args=[self.event.pk]))
        self.assertEqual(response.status_code,200)
        session=self.client.session
        request_key=session[f'checkout_{self.event.pk}']
        response=self.client.post(reverse('checkout',args=[self.event.pk]),{
            'customer_name':'Cliente de Teste',
            'email':'cliente-teste@example.com',
            'phone':'(11) 99999-9999',
            'document':'',
            'coupon_code':'',
            'quantity':'1',
            'terms':'on',
            'request_key':request_key,
            'website':'',
        })
        self.assertEqual(response.status_code,302)
        order=Order.objects.get(email='cliente-teste@example.com')
        self.assertEqual(order.payment_provider,'test')
        self.assertEqual(order.status,'pending')
        self.assertTrue(order.provider_pix_code.startswith('TESTE-'))

        response=self.client.post(reverse('confirm_test_payment',args=[order.pk]))
        self.assertEqual(response.status_code,302)
        order.refresh_from_db()
        self.assertEqual(order.status,'paid')
        self.event.refresh_from_db()
        self.assertEqual(self.event.sold,0)

        response=self.client.post(reverse('customer_login'),{'email':'cliente-teste@example.com'})
        self.assertEqual(response.status_code,302)
        code=self.client.session.get('customer_test_code')
        self.assertRegex(code,r'^\d{6}$')
        response=self.client.post(reverse('customer_verify'),{'code':code})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.session.get('customer_email'),'cliente-teste@example.com')


class EventCompetitionFormTests(TestCase):
    def data(self, **extra):
        dt=timezone.localtime(timezone.now()+timedelta(days=5))
        values={
            'title':'São Paulo x Adversário',
            'description':'Jogo teste',
            'category':'football',
            'competition':'brasileirao',
            'event_date':dt.date().isoformat(),
            'event_time':dt.strftime('%H:%M'),
            'price':'100.00',
            'capacity':'50',
            'max_per_order':'4',
            'ticket_source':'spfc',
            'ticket_source_notes':'',
            'doors_at':'',
            'location':'MorumBIS • São Paulo, SP',
            'includes':'',
            'food_info':'',
            'drinks_info':'',
            'parking_info':'',
            'age_rules':'',
            'status':'draft',
            'featured':'',
        }
        values.update(extra)
        return values

    def test_football_requires_competition(self):
        form=EventForm(data=self.data(competition=''))
        self.assertFalse(form.is_valid())
        self.assertIn('competition',form.errors)

    def test_football_accepts_competition(self):
        form=EventForm(data=self.data())
        self.assertTrue(form.is_valid(),form.errors)

    def test_concert_clears_competition(self):
        form=EventForm(data=self.data(category='concert',competition='brasileirao'))
        self.assertTrue(form.is_valid(),form.errors)
        event=form.save(commit=False)
        self.assertEqual(event.competition,'')
