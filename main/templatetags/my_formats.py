from django import template

register = template.Library()

@register.filter(name='decimal_with_comma')
def decimal_with_comma(value):
    return str(value).replace(".",",")