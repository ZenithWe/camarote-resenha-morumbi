from django import template
from decimal import Decimal
register=template.Library()
@register.filter
def brl(value):
    try: return 'R$ '+f'{Decimal(value):,.2f}'.replace(',','X').replace('.',',').replace('X','.')
    except Exception: return 'R$ 0,00'
@register.filter
def get_item(value,key): return value.get(key,'')
@register.filter
def lines(value): return [s.strip() for s in str(value).splitlines() if s.strip()]
@register.filter
def percentage(value,total): return min(100,round(float(value)/float(total)*100)) if total else 0
