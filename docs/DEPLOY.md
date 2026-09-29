# Publicar a plataforma Python

## Requisitos

- Python 3.12 e PostgreSQL.
- Hospedagem HTTPS, com domínio configurado.
- Armazenamento persistente para fotos, comprovantes e ingressos: volume persistente ou bucket **privado** compatível com S3.
- Credenciais definidas por variáveis de ambiente, nunca incluídas no GitHub.

Não use SQLite ou disco efêmero para vendas em produção. A aplicação bloqueia esse tipo de configuração por padrão.

## Serviço Python (por exemplo, Render)

Conecte este repositório na hospedagem e configure:

Build:

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
```

Antes do primeiro início, e quando existirem novas migrações:

```bash
python manage.py migrate --noinput
python manage.py seed_site
```

Start:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60
```

É possível usar um pre-deploy command para as migrações ou fazê-las no console da hospedagem. Não execute migrações em cada requisição.

Variáveis obrigatórias:

| Variável | Como preencher |
|---|---|
| `DEBUG` | `0` |
| `SECRET_KEY` | Gere 64 bytes aleatórios; não publique. |
| `DATABASE_URL` | Conexão PostgreSQL da sua hospedagem. |
| `ALLOWED_HOSTS` | Host exato do site, separado por vírgulas se houver mais de um. |
| `CSRF_TRUSTED_ORIGINS` | Origem HTTPS completa do site. |
| `TRUST_PROXY` | `1` somente quando o proxy confiável substituir o cabeçalho `X-Forwarded-Proto`. |
| `S3_BUCKET` | Nome do bucket privado, se usar S3. |
| `S3_ENDPOINT_URL` | Endpoint da conta para S3 compatível; vazio para AWS S3 padrão. |
| `S3_REGION` | Região do bucket. |
| `S3_ACCESS_KEY_ID` | Chave de acesso com permissão limitada ao bucket. |
| `S3_SECRET_ACCESS_KEY` | Segredo de acesso do armazenamento. |

A alternativa ao S3 é `PERSISTENT_MEDIA=1` com volumes realmente persistentes montados em `media/` e `private-media/`. Definir a variável sem montar o volume **não cria persistência**.

Crie o administrador pelo console seguro:

```bash
python manage.py createsuperuser
python manage.py check --deploy
```

Não use senha fixa no repositório ou em scripts. Acesso: `/painel/`.

## Docker Compose

Defina as variáveis em `.env`, com `DEBUG=0`, uma `SECRET_KEY` aleatória e `POSTGRES_PASSWORD` forte (use valor alfanumérico aleatório para a URL). O Compose cria PostgreSQL e volumes persistentes. O banco não publica uma porta externa; a aplicação é exposta somente em `127.0.0.1:8000` para um proxy HTTPS.

```bash
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
```

Configure seu proxy para fornecer HTTPS, encaminhar o host original e substituir `X-Forwarded-Proto`. Ative `TRUST_PROXY=1` somente nesse cenário. Limite o tamanho dos uploads no proxy (por exemplo, 24 MB por requisição). A aplicação valida individualmente as imagens de até 8 MB e PDFs de ingresso de até 10 MB. Galerias maiores podem ser enviadas em lotes.

## Operação

- Configure backup automático do PostgreSQL e dos arquivos privados, com teste de restauração.
- Não marque o bucket como público. URLs das imagens podem ser assinadas; comprovantes e ingressos são enviados pelo Django após verificar acesso.
- O endpoint `/saude/` retorna JSON simples para verificar o processo. Não atesta conectividade completa ao banco.
- Ajuste limites do proxy e proteção contra tráfego abusivo conforme o volume.
- Confirme o crédito em sua conta antes de marcar um pedido como pago. “Registrar reembolso” só deve ser usado após devolver o dinheiro.
- Revise regras, políticas, classificação etária, serviços incluídos, dados comerciais e canais de contato antes de vender.
- Substitua fotografias ilustrativas por fotos autorizadas do camarote, se disponíveis.
- Atualize periodicamente `requirements.txt` e rode os testes após atualizações.

## Limites desta entrega

- Nenhuma conta bancária, gateway ou emissor oficial de ingressos está conectado.
- Não há disparo automático de e-mails ou WhatsApp.
- O acesso ao pedido se dá pelo link privado mostrado após o checkout; o cliente deve guardá-lo. A equipe pode abrir esse link na tela do pedido para atendimento.
- Reembolsos são integrais; cancelamento de ingresso individual de um pedido não está implementado.
- O banco local e qualquer usuário usado para teste não são enviados ao GitHub.
