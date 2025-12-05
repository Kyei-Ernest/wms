from django.apps import AppConfig


class CollectorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'collector'

    
"""    def ready(self):
        ""Import signals when app is ready""
        import collector.signals  # noqa"""