from django.apps import AppConfig
import logging, os

logger = logging.getLogger(__name__)

class CrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crm'

    def ready(self) -> None:
        from . import signals
        if os.environ.get('RUN_MAIN') == 'true':
            from crm.tasks import cleanup_database
            cleanup_database.delay()
            