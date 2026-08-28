from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Look up a dict value by a variable key inside a template: {{ mydict|get_item:key }}"""
    if not dictionary:
        return None
    return dictionary.get(key)
