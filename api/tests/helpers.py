from django.contrib.auth.models import Permission
from django.db import IntegrityError


def create_permission_safely(codename, name, content_type):
    """
    Create a permission safely, handling any integrity errors.
    This method ensures we don't get UNIQUE constraint errors.
    """
    # First try to get the permission
    try:
        perm = Permission.objects.get(
            codename=codename,
            content_type=content_type
        )
        return perm
    except Permission.DoesNotExist:
        # If it doesn't exist, try to create it
        try:
            perm = Permission.objects.create(
                codename=codename,
                name=name,
                content_type=content_type
            )
            return perm
        except IntegrityError:
            # If we get an integrity error, someone else might have created it
            # Try one more time to get it
            return Permission.objects.get(
                codename=codename,
                content_type=content_type
            )
