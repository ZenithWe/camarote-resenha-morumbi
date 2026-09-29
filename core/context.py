from .models import SiteSettings
from .content import DEFAULT_TEXTS

def site_context(request):
    cfg=SiteSettings.objects.filter(pk=1).first()
    if cfg is None: cfg=SiteSettings()
    texts={**DEFAULT_TEXTS,**cfg.texts}
    return {'site':cfg,'copy':texts,'sales_ready':cfg.sales_enabled and bool(cfg.pix_key and cfg.pix_name),'instagram_handle':cfg.instagram.rstrip('/').split('/')[-1]}
