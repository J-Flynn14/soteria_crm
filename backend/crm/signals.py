from django.db.models.signals import post_delete, post_save, pre_save
from django.core.files.storage import default_storage
from django.db import transaction
from django.dispatch import receiver
from .models import Application, Candidate
from .tasks import cleanup_database
import logging
import threading

logger = logging.getLogger(__name__)

@receiver([post_save, post_delete], sender=Application, dispatch_uid="update_potential_candidates")
def update_potential_candidates(sender, instance, **kwargs):
    """
    Update the number of potential candidates for a Job when an Application is saved or deleted.
    This handler is lightweight and only performs a quick count update.
    """
    if instance.job:
        job = instance.job
        valid_applications_count = sender.objects.filter(job=job).exclude(application_status="Rejected").count()
        try:
            job.__class__.objects.filter(pk=job.pk).update(number_of_potential_candidates=valid_applications_count)
        except Exception as e:
            logger.error(f"Error updating potential candidates for Job ID {job.pk}: {e}")

_cleanup_flag = threading.local()

@receiver(post_delete, sender=Candidate, dispatch_uid="candidate_deleted_cleanup")
def candidate_deleted_cleanup(sender, instance, **kwargs):
    logger.info(f"Candidate {instance.pk} deleted; scheduling cleanup on commit.")

    if not getattr(_cleanup_flag, 'already_scheduled', False):
        _cleanup_flag.already_scheduled = True

        def run_cleanup():
            cleanup_database.delay()
            _cleanup_flag.already_scheduled = False
        transaction.on_commit(run_cleanup)
