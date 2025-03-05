from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def has_investigation_permission(context, permission):
    investigation = context.get('investigation')
    user = context['request'].user
    if investigation:
        if permission == 'read':
            return investigation.can_read(user)
        elif permission == 'write':
            return investigation.can_write(user)
    return False