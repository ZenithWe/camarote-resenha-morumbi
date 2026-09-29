from datetime import datetime, time
from zoneinfo import ZoneInfo
from decimal import Decimal
from django.db import migrations

TZ = ZoneInfo("America/Sao_Paulo")
PREFIX = "[TESTE]"

EVENTS = [
    {
        "title": "[TESTE] Jogo 1 — São Paulo x Time Visitante",
        "description": "Evento fictício criado apenas para testar a agenda pública e o fluxo de vendas do Camarote Resenha Morumbi.",
        "category": "football",
        "starts_at": datetime(2026, 10, 3, 18, 30, tzinfo=TZ),
        "doors_at": time(16, 30),
        "price": Decimal("299.90"),
    },
    {
        "title": "[TESTE] Jogo 2 — São Paulo x Time Visitante",
        "description": "Evento fictício criado apenas para testar a agenda pública e o fluxo de vendas do Camarote Resenha Morumbi.",
        "category": "football",
        "starts_at": datetime(2026, 10, 10, 20, 0, tzinfo=TZ),
        "doors_at": time(18, 0),
        "price": Decimal("319.90"),
    },
    {
        "title": "[TESTE] Jogo 3 — São Paulo x Time Visitante",
        "description": "Evento fictício criado apenas para testar a agenda pública e o fluxo de vendas do Camarote Resenha Morumbi.",
        "category": "football",
        "starts_at": datetime(2026, 10, 17, 16, 0, tzinfo=TZ),
        "doors_at": time(14, 0),
        "price": Decimal("289.90"),
    },
    {
        "title": "[TESTE] Show 1 — Artista Convidado",
        "description": "Evento fictício criado apenas para testar a agenda pública e o fluxo de vendas do Camarote Resenha Morumbi.",
        "category": "concert",
        "starts_at": datetime(2026, 10, 5, 21, 0, tzinfo=TZ),
        "doors_at": time(18, 30),
        "price": Decimal("399.90"),
    },
    {
        "title": "[TESTE] Show 2 — Artista Convidado",
        "description": "Evento fictício criado apenas para testar a agenda pública e o fluxo de vendas do Camarote Resenha Morumbi.",
        "category": "concert",
        "starts_at": datetime(2026, 10, 12, 20, 30, tzinfo=TZ),
        "doors_at": time(18, 0),
        "price": Decimal("429.90"),
    },
    {
        "title": "[TESTE] Show 3 — Artista Convidado",
        "description": "Evento fictício criado apenas para testar a agenda pública e o fluxo de vendas do Camarote Resenha Morumbi.",
        "category": "concert",
        "starts_at": datetime(2026, 10, 19, 21, 30, tzinfo=TZ),
        "doors_at": time(19, 0),
        "price": Decimal("449.90"),
    },
]


def create_test_events(apps, schema_editor):
    Event = apps.get_model("core", "Event")
    for item in EVENTS:
        Event.objects.get_or_create(
            title=item["title"],
            defaults={
                "description": item["description"],
                "category": item["category"],
                "starts_at": item["starts_at"],
                "doors_at": item["doors_at"],
                "price": item["price"],
                "capacity": 50,
                "max_per_order": 8,
                "ticket_source": "other",
                "ticket_source_notes": "Evento fictício para demonstração.",
                "location": "MorumBIS • São Paulo, SP",
                "includes": "Acesso ao camarote\nAmbiente exclusivo\nAtendimento da equipe",
                "age_rules": "Evento de teste. Regras reais devem ser cadastradas antes da venda.",
                "status": "published",
                "featured": False,
            },
        )


def remove_test_events(apps, schema_editor):
    Event = apps.get_model("core", "Event")
    Event.objects.filter(title__startswith=PREFIX).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_event_ticket_source_orderticket"),
    ]

    operations = [
        migrations.RunPython(create_test_events, remove_test_events),
    ]
