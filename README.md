# Camarote Resenha Morumbi

Plataforma de ingressos em **Python 3.12 + Django 5.2 LTS**, com HTML semântico, CSS responsivo e JavaScript. PostgreSQL em produção. Instagram: [@resenhamorumbi](https://www.instagram.com/resenhamorumbi/).

## O que está incluído

- Site com jogos do São Paulo, shows, páginas de evento e filtros por categoria.
- Painel exclusivo para administrador, com login, troca de senha e bloqueio de tentativas repetidas.
- Criar/editar/excluir eventos: nome, descrição, categoria, preço, estoque total, fotos, galeria, data, horário, abertura do camarote, itens incluídos e regras.
- **Agenda mensal**, com navegação entre meses, indicação do dia atual e lista de eventos do mês. O cadastro oferece campo e botão para escolher a data no calendário.
- Estoque compartilhado com os pedidos: reservas de 30 minutos, limite por pedido e bloqueio transacional no PostgreSQL.
- Checkout com nome, e-mail, telefone e aceite das informações da compra.
- Pix com QR Code e Copia e Cola por pedido, upload privado de comprovante e **conferência manual** do pagamento.
- Pedidos com status, filtros, exportação CSV e PDF de ingresso oficial anexado pelo administrador.
- Financeiro: receita confirmada, quantidade de ingressos vendidos, pendências, reembolsos, taxas, despesas, retiradas e saldo registrado.
- CMS para textos, botões, navegação, dúvidas, informações da compra e etapas do checkout.
- Banners com imagem, texto, botão, link, ordem e visibilidade.
- Substituição de logo e imagens das seções.
- Registro de ações administrativas.

Não são criados eventos, preços ou vendas fictícios. As fotografias iniciais são ilustrativas do estádio e de evento anterior. As vendas começam desativadas.

## Executar no computador

Instale Python 3.12 ou superior. Na pasta do projeto:

```bash
python -m venv .venv
```

Ative o ambiente:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux ou macOS
source .venv/bin/activate
```

Depois:

```bash
pip install -r requirements.txt
python setup_local.py
python manage.py createsuperuser
python manage.py runserver
```

- Site: `http://127.0.0.1:8000/`
- Painel: `http://127.0.0.1:8000/painel/`

O script local gera uma chave secreta exclusiva no `.env`. **Não existe usuário ou senha padrão.** Escolha seu próprio acesso no comando `createsuperuser`.

## Primeiro uso

1. Entre no painel com seu usuário administrador.
2. Em **Configurações**, cadastre contato, chave Pix, nome e cidade do recebedor. Não ative as vendas antes de revisar os dados.
3. Em **Eventos → Criar evento**, preencha os dados, escolha o dia no calendário e defina o horário de Brasília.
4. Salve como rascunho para revisar. Quando estiver pronto, altere para publicado.
5. Atualize os textos, fotos reais do camarote e banners.
6. Revise as regras do evento e as informações da compra, habilite as vendas e faça uma compra de teste controlada antes de divulgar.
7. Após conferir um Pix na conta, confirme o pedido e anexe o PDF oficial do ingresso.

## Como o dinheiro e os ingressos são controlados

**Saldo registrado = pagamentos confirmados − reembolsos integrais − taxas registradas − despesas − retiradas.**

Este sistema não acessa sua conta bancária e não efetua transferências, saques ou reembolsos. As ações financeiras registram operações já conferidas ou realizadas por você. O checkout usa Pix com confirmação manual; não existe integração com gateway ou confirmação bancária automática nesta versão.

Reservas pendentes ocupam estoque por 30 minutos. Depois disso, deixam de consumir estoque. Quando o cliente envia o comprovante a tempo, o pedido entra em análise e mantém a reserva até decisão da equipe. Confirmação tardia só é permitida se ainda houver estoque. Cancelar ou registrar reembolso libera a quantidade. O preço é calculado no servidor e preservado no pedido.

A página do pedido é um comprovante; não é um ingresso válido para o estádio. Apenas o PDF oficial anexado pela equipe deve ser usado para acesso. O link privado do pedido funciona como um segredo de acesso de alta entropia: compartilhe-o somente com o titular.

## Publicação

**GitHub armazena o código; GitHub Pages não executa o servidor Python.** Use uma hospedagem compatível com Django, por exemplo um serviço Python no Render ou um servidor com Docker, PostgreSQL e HTTPS.

Consulte [docs/DEPLOY.md](docs/DEPLOY.md). A aplicação se recusa a iniciar em produção sem chave segura, PostgreSQL e configuração de armazenamento persistente. A hospedagem, domínio, banco e armazenamento devem ser contratados/configurados na conta do responsável.

## Segurança implementada

- Sessões no servidor, senhas com hash do Django, sem senhas no JavaScript.
- Todas as rotas administrativas verificam no servidor se o usuário é superusuário ativo.
- Proteção CSRF nos formulários, autoescape dos templates, ORM parametrizado, CSP e bloqueio de iframes.
- Cookies Secure e HttpOnly, HTTPS e HSTS em produção; validação de hosts.
- Limitação de tentativas de login via django-axes e de criação de pedidos por IP/e-mail.
- Imagens verificadas e reencodadas como WebP, sem metadados ou conteúdo adicional. SVG/HTML não são aceitos como uploads.
- Comprovantes e ingressos separados das imagens públicas, sem URL pública de arquivo.
- Bloqueios transacionais de estoque; idempotência de checkout; valores em Decimal.
- Neutralização de fórmulas no CSV.

A segurança também depende de atualizações, HTTPS, backups, permissões e configuração da hospedagem. CPF e dados de cartão não são coletados. O formulário verifica o formato do contato, não comprova a titularidade de um e-mail/telefone.

## Testes

```bash
python manage.py check
python manage.py test tests
```

Testes cobrem acesso, CSRF, estoque, idempotência, preço no servidor, expiração, comprovantes, arquivos privados, Pix, financeiro, calendário, edição de estoque e CMS. O CI usa PostgreSQL. A validação local foi feita com SQLite; a aplicação exige PostgreSQL em produção para bloqueio concorrente real.

## Estrutura

```text
config/               Configurações, URLs e WSGI
core/                 Modelos, formulários, serviços e telas
core/migrations/      Estrutura versionada do banco
templates/            Site, painel e autenticação
static/               CSS, JavaScript, favicon e imagens
tests/               Testes funcionais
docs/                Guia de implantação e créditos
```

As fotos mantêm suas licenças próprias: [docs/CREDITOS.md](docs/CREDITOS.md). Nenhuma licença de código aberto foi atribuída automaticamente ao projeto.
