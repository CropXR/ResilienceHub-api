from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        """Run when the app is ready."""
        from django.contrib import admin
        from rest_framework.authtoken.models import Token

        # Unregister the default Token admin if it's registered
        # This must be done in ready() to ensure authtoken has already registered it
        if admin.site.is_registered(Token):
            admin.site.unregister(Token)
