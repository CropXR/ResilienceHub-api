from django.contrib.auth.models import User
from guardian.core import ObjectPermissionChecker

from ..choices import SecurityLevel
from api.models import Investigation


# for each model
    # implement each method
        # check permission needed
        # interact with db models


class InvestigationService:

    @staticmethod
    def list(user: User):
        # get_objects_for_user()
        base_queryset = Investigation.objects.all()

        checker = ObjectPermissionChecker(user)
        checker.prefetch_perms(base_queryset)

        visible_ids = [
            inv.id for inv in base_queryset
            if checker.has_perm('api.view_investigation', inv) and
               # Apply confidentiality filtering
               (inv.security_level != SecurityLevel.CONFIDENTIAL or
                user.has_perm('api.view_investigation', inv))
        ]
        # nice exception handling

        return base_queryset.filter(id__in=visible_ids).order_by('id')
