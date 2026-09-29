from .models import SiteSettings
from .content import DEFAULT_TEXTS

def site_context(request):
    cfg=SiteSettings.objects.filter(pk=1).first()
    if cfg is None: cfg=SiteSettings()
    texts={**DEFAULT_TEXTS,**cfg.texts}
    from django.conf import settings
    provider=getattr(settings,'PAYMENT_PROVIDER','manual')
    if provider=='pagarme': gateway_ready=getattr(settings,'PAGARME_CONFIGURED',False)
    elif provider=='mercadopago': gateway_ready=getattr(settings,'MERCADOPAGO_CONFIGURED',False)
    else: gateway_ready=bool(cfg.pix_key and cfg.pix_name and cfg.pix_city)
    admin_test_mode=bool(getattr(request,'user',None) and request.user.is_authenticated and request.user.is_superuser and request.session.get('admin_test_mode') is True)
    sales_ready=(cfg.sales_enabled and gateway_ready) or admin_test_mode
    return {'site':cfg,'copy':texts,'sales_ready':sales_ready,'payment_provider':provider,'pagarme_ready':getattr(settings,'PAGARME_CONFIGURED',False),'mercadopago_ready':getattr(settings,'MERCADOPAGO_CONFIGURED',False),'admin_test_mode':admin_test_mode,'site_url':getattr(settings,'SITE_URL',''),'instagram_handle':cfg.instagram.rstrip('/').split('/')[-1]}
