from django.apps import AppConfig

class YourAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'isa_api' 

    def ready(self):
        """Connect signals when the app is ready"""
        import api.signals
        