from django import template

register = template.Library()

@register.filter
def can_write(investigation, user):
    """
    Template filter to check if a user can write to an investigation
    """
    return investigation.can_write(user)