from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from .models import InvestigationPermission, StudyPermission
from .choices import UserRole

@receiver(pre_delete, sender=InvestigationPermission)
def prevent_delete_last_investigation_owner(sender, instance, **kwargs):
    """
    Allow deletion if investigation is being deleted.
    Prevent removing the last owner if the investigation is not being deleted.
    """
    if instance.role == UserRole.OWNER:
        # Count owners for this investigation
        owner_count = InvestigationPermission.objects.filter(
            investigation=instance.investigation,
            role=UserRole.OWNER
        ).count()
        
        # If this is the last owner and the investigation is not being deleted
        if owner_count <= 1:
            # Check if the investigation is also being deleted
            try:
                instance.investigation  # This will trigger an error if investigation is deleted
                raise ValidationError(
                    "Cannot remove the last owner. Assign another owner first."
                )
            except:
                # If investigation is already deleted, allow this permission to be deleted
                pass

# Signal to prevent removal of the last owner of a study
@receiver(pre_delete, sender=StudyPermission)
def prevent_delete_last_study_owner(sender, instance, **kwargs):
    """Prevent deletion of the last owner permission for a study."""
    if instance.role == UserRole.OWNER:
        owner_count = StudyPermission.objects.filter(
            study=instance.study,
            role=UserRole.OWNER
        ).count()
        
        if owner_count <= 1:
            raise ValidationError(
                "Cannot remove the last owner. Assign another owner first."
            )