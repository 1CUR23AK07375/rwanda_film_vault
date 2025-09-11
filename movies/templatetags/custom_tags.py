# movies/templatetags/custom_tags.py
from django import template
from django.utils.timesince import timesince
from django.utils.timezone import now

register = template.Library()

@register.filter
def time_ago(value):
    if not value:
        return ""
    return timesince(value, now()) + " ago"
