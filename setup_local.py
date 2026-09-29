"""Configuração local sem credenciais fixas. Execute após instalar requirements.txt."""
import os, secrets, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parent
os.chdir(root)
env=root/'.env'
if not env.exists():
    env.write_text('DEBUG=1\nSECRET_KEY='+secrets.token_urlsafe(64)+'\nALLOWED_HOSTS=localhost,127.0.0.1\n',encoding='utf-8')
    try: env.chmod(0o600)
    except OSError: pass
for command in [['migrate'],['seed_site']]:
    subprocess.run([sys.executable,'manage.py',*command],check=True)
print('\nAgora crie seu acesso com: python manage.py createsuperuser')
print('Depois abra o site com: python manage.py runserver')
