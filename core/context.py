from .models import SiteSettings
from .content import DEFAULT_TEXTS

def site_context(request):
    cfg=SiteSettings.objects.filter(pk=1).first()
    if cfg is None: cfg=SiteSettings()
    texts={**DEFAULT_TEXTS,**cfg.texts}
    from django.conf import settings
    provider=getattr(settings,'PAYMENT_PROVIDER','manual')
    gateway_ready=getattr(settings,'PAGARME_CONFIGURED',False) if provider=='pagarme' else bool(cfg.pix_key and cfg.pix_name and cfg.pix_city)
    return {'site':cfg,'copy':texts,'sales_ready':cfg.sales_enabled and gateway_ready,'payment_provider':provider,'pagarme_ready':getattr(settings,'PAGARME_CONFIGURED',False),'instagram_handle':cfg.instagram.rstrip('/').split('/')[-1]}
