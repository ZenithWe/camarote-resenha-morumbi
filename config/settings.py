import os, sys, secrets
from pathlib import Path
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
DEBUG = os.getenv('DEBUG', '0') == '1'
IS_COLLECTSTATIC = 'collectstatic' in sys.argv
SECRET_KEY = os.getenv('SECRET_KEY', '')
if len(SECRET_KEY) < 50:
    if DEBUG:
        raise ImproperlyConfigured('Defina SECRET_KEY com pelo menos 50 caracteres. Execute python setup_local.py para uso local.')
    # Fallback seguro para plataformas onde o segredo ainda não foi cadastrado:
    # cria uma chave aleatória local, não versionada e reutilizada por todos os
    # processos do mesmo deploy. Uma SECRET_KEY persistente no ambiente continua
    # sendo a opção recomendada para evitar logout após um novo deploy.
    secret_file = BASE_DIR / '.runtime-secret-key'
    try:
        SECRET_KEY = secret_file.read_text(encoding='utf-8').strip()
    except (FileNotFoundError, OSError):
        SECRET_KEY = ''
    if len(SECRET_KEY) < 50:
        generated = secrets.token_urlsafe(64)
        try:
            fd = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(generated)
            SECRET_KEY = generated
        except FileExistsError:
            SECRET_KEY = secret_file.read_text(encoding='utf-8').strip()
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured('Não foi possível obter uma SECRET_KEY segura.')
ALLOWED_HOSTS = [s.strip() for s in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if s.strip()]
CSRF_TRUSTED_ORIGINS = [s.strip() for s in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if s.strip()]
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','axes','core']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware','axes.middleware.AxesMiddleware','core.middleware.SecurityHeadersMiddleware']
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','core.context.site_context']}}]
WSGI_APPLICATION='config.wsgi.application'
DATABASES={'default':dj_database_url.config(default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',conn_max_age=60,conn_health_checks=True)}
if not DEBUG and not IS_COLLECTSTATIC and DATABASES['default']['ENGINE'].endswith('sqlite3'):
    raise ImproperlyConfigured('Em produção, configure DATABASE_URL com PostgreSQL para controle concorrente de estoque.')
if DATABASES['default']['ENGINE'].endswith('sqlite3'):
    DATABASES['default']['OPTIONS']={'timeout':20}
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
AUTHENTICATION_BACKENDS=['axes.backends.AxesStandaloneBackend','django.contrib.auth.backends.ModelBackend']
AXES_FAILURE_LIMIT=5
AXES_COOLOFF_TIME=timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS=['username','ip_address']
AXES_RESET_ON_SUCCESS=True
AXES_CLIENT_IP_CALLABLE=lambda request: request.META.get('REMOTE_ADDR')
AXES_LOCKOUT_TEMPLATE='registration/locked.html'
LANGUAGE_CODE='pt-br'
TIME_ZONE='America/Sao_Paulo'
USE_I18N=True
USE_TZ=True
STATIC_URL='/static/'
STATIC_ROOT=BASE_DIR/'staticfiles'
STATICFILES_DIRS=[BASE_DIR/'static']
MEDIA_URL='/media/'
MEDIA_ROOT=BASE_DIR/'media'
PRIVATE_MEDIA_ROOT=BASE_DIR/'private-media'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='/painel/entrar/'
LOGIN_REDIRECT_URL='/painel/'
LOGOUT_REDIRECT_URL='/'
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Lax'
SESSION_COOKIE_AGE=7200
SESSION_EXPIRE_AT_BROWSER_CLOSE=True
CSRF_COOKIE_HTTPONLY=True
CSRF_COOKIE_SAMESITE='Lax'
SECURE_SSL_REDIRECT=not DEBUG
SESSION_COOKIE_SECURE=not DEBUG
CSRF_COOKIE_SECURE=not DEBUG
SECURE_HSTS_SECONDS=31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY='same-origin'
X_FRAME_OPTIONS='DENY'
if os.getenv('TRUST_PROXY','0')=='1':
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
DATA_UPLOAD_MAX_MEMORY_SIZE=12*1024*1024
FILE_UPLOAD_MAX_MEMORY_SIZE=2*1024*1024
STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'whitenoise.storage.CompressedManifestStaticFilesStorage'},'private':{'BACKEND':'django.core.files.storage.FileSystemStorage','OPTIONS':{'location':PRIVATE_MEDIA_ROOT}}}
if os.getenv('S3_BUCKET'):
    S3_OPTIONS={'bucket_name':os.environ['S3_BUCKET'],'endpoint_url':os.getenv('S3_ENDPOINT_URL') or None,'region_name':os.getenv('S3_REGION','us-east-1'),'access_key':os.environ['S3_ACCESS_KEY_ID'],'secret_key':os.environ['S3_SECRET_ACCESS_KEY'],'default_acl':None,'file_overwrite':False,'querystring_auth':True}
    STORAGES['default']={'BACKEND':'storages.backends.s3.S3Storage','OPTIONS':{**S3_OPTIONS,'location':'public-images'}}
    STORAGES['private']={'BACKEND':'storages.backends.s3.S3Storage','OPTIONS':{**S3_OPTIONS,'location':'private'}}
elif not DEBUG and not IS_COLLECTSTATIC and os.getenv('PERSISTENT_MEDIA','0')!='1':
    raise ImproperlyConfigured('Configure S3_BUCKET ou PERSISTENT_MEDIA=1 com disco persistente para preservar os uploads.')
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST=os.getenv('EMAIL_HOST','')
EMAIL_PORT=int(os.getenv('EMAIL_PORT','587'))
EMAIL_USE_TLS=True
EMAIL_HOST_USER=os.getenv('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD=os.getenv('EMAIL_HOST_PASSWORD','')
DEFAULT_FROM_EMAIL=os.getenv('DEFAULT_FROM_EMAIL','')
