from datetime import datetime
from zoneinfo import ZoneInfo
from django.db import migrations
from django.db.models import Q

TZ=ZoneInfo('America/Sao_Paulo')

GAMES=[
    {
        'title':'São Paulo x Santos',
        'starts_at':datetime(2026,10,2,20,0,tzinfo=TZ),
        'description':'Clássico no MorumBIS! São Paulo e Santos se enfrentam pelo Campeonato Brasileiro 2026. Viva a partida com a experiência do Camarote Resenha Morumbi, em um ambiente reservado para acompanhar cada momento do jogo com mais conforto e praticidade.',
        'includes':'Acesso ao Camarote Resenha Morumbi\nExperiência de jogo no MorumBIS\nAmbiente reservado durante o evento',
    },
    {
        'title':'São Paulo x Vitória',
        'starts_at':datetime(2026,10,10,21,0,tzinfo=TZ),
        'description':'Noite de Campeonato Brasileiro no MorumBIS. O São Paulo recebe o Vitória em mais uma partida importante da temporada 2026. Acompanhe o jogo pelo Camarote Resenha Morumbi e aproveite uma experiência preparada para curtir o estádio com conforto e clima de decisão.',
        'includes':'Acesso ao Camarote Resenha Morumbi\nExperiência de jogo no MorumBIS\nAmbiente reservado durante o evento',
    },
    {
        'title':'São Paulo x Vasco',
        'starts_at':datetime(2026,10,17,21,0,tzinfo=TZ),
        'description':'São Paulo e Vasco frente a frente no MorumBIS pelo Campeonato Brasileiro 2026. Uma noite de futebol para viver de perto a atmosfera do estádio no Camarote Resenha Morumbi, com um espaço reservado para aproveitar o evento do início ao fim.',
        'includes':'Acesso ao Camarote Resenha Morumbi\nExperiência de jogo no MorumBIS\nAmbiente reservado durante o evento',
    },
]

def organize_events(apps,schema_editor):
    Event=apps.get_model('core','Event')
    Order=apps.get_model('core','Order')

    keep_gusttavo=Q(title__icontains='gusttavo lima')|Q(title__icontains='gustavo lima')
    desired_titles=[game['title'] for game in GAMES]
    removable=Event.objects.exclude(keep_gusttavo).exclude(title__in=desired_titles)

    deleted=0
    preserved=0
    for event in list(removable):
        # Pedidos do modo de teste não precisam manter o evento.
        Order.objects.filter(event_id=event.pk,payment_provider='test').delete()
        # Nunca apagamos histórico financeiro real automaticamente.
        if Order.objects.filter(event_id=event.pk).exists():
            event.status='closed'
            event.save(update_fields=['status'])
            preserved+=1
            continue
        event.delete()
        deleted+=1

    for game in GAMES:
        Event.objects.update_or_create(
            title=game['title'],
            defaults={
                'description':game['description'],
                'category':'football',
                'competition':'brasileirao',
                'starts_at':game['starts_at'],
                'doors_at':None,
                # Valores temporários somente para satisfazer o schema.
                # O evento permanece em rascunho e não é vendido até o ADM definir preço/estoque.
                'price':'1.00',
                'capacity':1,
                'max_per_order':8,
                'ticket_source':'spfc',
                'ticket_source_notes':'Definir preço e carregar o estoque oficial antes de publicar.',
                'location':'MorumBIS • São Paulo, SP',
                'includes':game['includes'],
                'food_info':'',
                'drinks_info':'',
                'parking_info':'',
                'age_rules':'Regras de acesso e classificação conforme as determinações oficiais do evento e do MorumBIS.',
                'status':'draft',
                'featured':False,
            },
        )
    print(f'[eventos-outubro] removidos={deleted} preservados_por_historico={preserved} jogos_cadastrados={len(GAMES)}')

def reverse_noop(apps,schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies=[
        ('core','0010_event_competition'),
    ]
    operations=[
        migrations.RunPython(organize_events,reverse_noop),
    ]
