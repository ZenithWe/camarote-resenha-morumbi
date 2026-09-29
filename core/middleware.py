class SecurityHeadersMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        response=self.get_response(request)
        response['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        response['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        if request.path.startswith(('/painel/','/pedido/','/checkout/','/admin/')):
            response['Cache-Control']='private, no-store, max-age=0'
            response['Referrer-Policy']='no-referrer'
            response['X-Robots-Tag']='noindex, nofollow'
        return response
