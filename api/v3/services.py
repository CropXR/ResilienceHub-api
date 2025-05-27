from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from guardian.core import ObjectPermissionChecker
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import Serializer

from ..choices import SecurityLevel
from api.models import Investigation
from ..permissions import GuardianMixin, ROLE_PERMISSIONS

class InvestigationService:

    @staticmethod
    def list(user: User) -> list[Investigation]:
        # return get_objects_for_user(user, 'api.view_investigation')

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

        return base_queryset.filter(id__in=visible_ids).order_by('id')

    @staticmethod
    def get(user: User, accession_code: str) -> Investigation:
        try:
            investigation = Investigation.objects.get(accession_code=accession_code)
        except Investigation.DoesNotExist:
            raise Http404

        if not user.has_perm('api.view_investigation', investigation):
            raise PermissionDenied

        return investigation

    @staticmethod
    def create(user: User, serializer: Serializer):
        investigation = serializer.save()
        assign_owner_permissions_to_model(investigation, model_name="investigation", user=user)


def assign_owner_permissions_to_model(
    guardian_model: GuardianMixin, model_name: str, user: User
):
    role = 'owner'
    content_type = ContentType.objects.get_for_model(guardian_model)

    for perm_type in ROLE_PERMISSIONS[role]:
        codename = f'{perm_type}_{model_name}'
        # Ensure permissions exist before assigning
        Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={'name': f'Can {perm_type} {model_name}'}
        )
        assign_perm(codename, user, guardian_model)

    guardian_model.set_user_role(user, role)
