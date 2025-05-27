# api/v1/views.py
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.http import Http404
from guardian.shortcuts import assign_perm
from guardian.shortcuts import get_users_with_perms
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .serializers import (
    InvestigationSerializer,
    StudySerializer,
    AssaySerializer,
    SampleSerializer,
)
from ..choices import SecurityLevel
from api.models import UserRole, Investigation, Study, Assay, Sample
from ..permissions import GuardianPermission, IsOwnerOrAdmin
from ..permissions import (
    ROLE_PERMISSIONS
)


class StudyPermissionOverrideMixin:
    """
    A mixin to override the default behavior of DRF's get_object
    to ensure proper error handling (403 vs 404) for permission checks.
    """
    def get_object(self):
        """
        Override get_object to return 403 instead of 404 for unauthorized access.
        This ensures that objects that exist but can't be accessed return 403 Forbidden
        instead of 404 Not Found.
        """
        # Get the lookup field value
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        
        # Try to get the object without any visibility filtering
        try:
            # Get the basic queryset without visibility filtering
            queryset = self.get_queryset().model.objects.all()
            
            # Get the object
            obj = queryset.get(**{self.lookup_field: lookup_value})
            
            # Check permissions - this raises PermissionDenied (403) if not allowed
            self.check_object_permissions(self.request, obj)
            
            return obj
        except self.queryset.model.DoesNotExist:
            # Object truly doesn't exist
            raise Http404
        except PermissionDenied:
            # Re-raise permission denied to show 403 instead of 404
            raise

class InvestigationViewSet(viewsets.ModelViewSet):
    permission_classes = [GuardianPermission]
    queryset = Investigation.objects.all()
    serializer_class = InvestigationSerializer
    lookup_field = 'accession_code'
    lookup_value_regex = 'CXRP[0-9]+'

    def get_object(self):
        try:
            # First try to get the object
            investigation = Investigation.objects.get(
                accession_code=self.kwargs[self.lookup_field]
            )
            
            # If we found it, check permissions
            if not investigation.can_read(self.request.user):
                raise PermissionDenied
                
            return investigation
            
        except Investigation.DoesNotExist:
            raise Http404

    def get_queryset(self):
        user = self.request.user
        base_queryset = Investigation.objects.all()

        # Add visibility filters based on can_read
        visible_investigations = [
            inv for inv in base_queryset
            if inv.can_read(user)
        ]
        
        # Convert filtered list back to queryset
        visible_ids = [inv.id for inv in visible_investigations]
        return base_queryset.filter(id__in=visible_ids).order_by('id')
    
    def perform_create(self, serializer):
        # Set the current user as owner when creating a new investigation
        investigation = serializer.save()
        
        # Get the content type for Investigation
        content_type = ContentType.objects.get_for_model(investigation)
        
        # Ensure permissions exist
        for perm_type in ROLE_PERMISSIONS['owner']:
            # Construct the full permission codename
            codename = f'{perm_type}_investigation'
            
            # Create the permission if it doesn't exist
            Permission.objects.get_or_create(
                content_type=content_type,
                codename=codename,
                defaults={'name': f'Can {perm_type} investigation'}
            )
            
            # Assign the permission
            assign_perm(codename, self.request.user, investigation)
        
        # Store role information
        investigation.set_user_role(self.request.user, 'owner')


class StudyViewSet(viewsets.ModelViewSet):
    permission_classes = [GuardianPermission]
    queryset = Study.objects.all()
    serializer_class = StudySerializer
    lookup_field = 'accession_code'
    lookup_value_regex = 'CXRS[0-9]+'

    def get_queryset(self):
        queryset = Study.objects.all()
        
        # Handle nested route
        investigation_accession = self.kwargs.get('investigation_accession_code')
        if investigation_accession:
            try:
                investigation = Investigation.objects.get(accession_code=investigation_accession)
                # Explicitly check if any studies exist for this investigation
                queryset = queryset.filter(investigation__accession_code=investigation_accession)
                if not queryset.exists():
                    raise Http404("No studies found for this investigation")
            except Investigation.DoesNotExist:
                raise Http404("Investigation not found")

        user = self.request.user
        
        # Superuser sees everything
        if user.is_superuser:
            return queryset

        # Permission filters
        filters = models.Q(security_level=SecurityLevel.PUBLIC)

        if user.is_authenticated:
            if user.is_staff:
                filters |= models.Q(security_level=SecurityLevel.INTERNAL)
            
            # User-specific access - adapt to use get_users_with_perms
            visible_studies = []
            for study in queryset:
                if study.can_read(user):
                    visible_studies.append(study.id)
            
            if visible_studies:
                filters |= models.Q(id__in=visible_studies)

        return queryset.filter(filters).distinct()

    def get_object(self):
        """
        Override to ensure 403 instead of 404 for permission denied cases
        Also ensures that staff users can access internal studies
        """
        # Get lookup fields from URL
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        
        # First check if this is a nested route with investigation
        if 'investigation' in self.kwargs:
            investigation_code = self.kwargs['investigation']
            study_code = self.kwargs[lookup_url_kwarg]
            
            # Get both objects directly - bypassing any filtering
            try:
                investigation = Investigation.objects.get(accession_code=investigation_code)
                
                # Try to get the study directly from database
                try:
                    study = Study.objects.get(
                        investigation=investigation,
                        accession_code=study_code
                    )
                    
                    # Special logic for staff users with internal studies
                    if self.request.user.is_staff and study.security_level == SecurityLevel.INTERNAL:
                        # Staff users should always be able to access internal studies
                        # Check if they have permission on the investigation
                        if investigation.can_read(self.request.user):
                            return study
                    
                    # Check permissions explicitly
                    if not study.can_read(self.request.user):
                        raise PermissionDenied("You do not have permission to access this study.")
                    
                    return study
                except Study.DoesNotExist:
                    raise Http404("Study not found")
            except Investigation.DoesNotExist:
                raise Http404("Investigation not found")
        
        # Fall back to standard behavior for other cases
        return super().get_object()
        
    def list(self, request, *args, **kwargs):
        """
        Override list to properly handle study listing within an investigation
        Ensures staff users can see internal studies
        """
        # If filtering by investigation
        if 'investigation' in self.kwargs:
            investigation_code = self.kwargs['investigation']
            
            try:
                investigation = Investigation.objects.get(accession_code=investigation_code)
                
                # Check if user can access the investigation
                if not investigation.can_read(request.user):
                    raise PermissionDenied("You do not have permission to access this investigation.")
                
                # Get all studies for this investigation
                all_studies = Study.objects.filter(investigation=investigation)
                
                # Special handling for staff users
                if request.user.is_staff:
                    # Staff can see public and internal studies in this investigation
                    visible_studies = [study for study in all_studies if 
                                    study.security_level in [SecurityLevel.PUBLIC, SecurityLevel.INTERNAL] or
                                    study.can_read(request.user)]
                else:
                    # Regular users - filter based on permissions
                    visible_studies = [study for study in all_studies if study.can_read(request.user)]
                
                # Use the serializer directly
                page = self.paginate_queryset(visible_studies)
                if page is not None:
                    serializer = self.get_serializer(page, many=True)
                    return self.get_paginated_response(serializer.data)
                
                serializer = self.get_serializer(visible_studies, many=True)
                return Response(serializer.data)
                
            except Investigation.DoesNotExist:
                raise Http404("Investigation not found")
        
        # Fall back to default behavior
        return super().list(request, *args, **kwargs)
            
    def perform_create(self, serializer):
        # Set the current user as owner when creating a new study
        study = serializer.save()
        study.assign_role(self.request.user, UserRole.OWNER)


class AssayViewSet(viewsets.ModelViewSet):
    permission_classes = [GuardianPermission]
    serializer_class = AssaySerializer
    lookup_field = 'accession_code'
    lookup_value_regex = 'CXRA[0-9]+'

    def get_queryset(self):
        queryset = Assay.objects.all()
        
        # Validate nested routes
        investigation_accession = self.kwargs.get('investigation_accession_code')
        study_accession = self.kwargs.get('study_accession_code')
        
        if investigation_accession:
            try:
                investigation = Investigation.objects.get(accession_code=investigation_accession)
                queryset = queryset.filter(study__investigation__accession_code=investigation_accession)
                if not queryset.exists():
                    raise Http404("No assays found for this investigation")
            except Investigation.DoesNotExist:
                raise Http404("Investigation not found")
        
        if study_accession:
            try:
                study = Study.objects.get(accession_code=study_accession)
                # Additional check to ensure study matches investigation if both are provided
                if investigation_accession:
                    if study.investigation.accession_code != investigation_accession:
                        raise Http404("Study does not belong to the specified investigation")
                queryset = queryset.filter(study__accession_code=study_accession)
                if not queryset.exists():
                    raise Http404("No assays found for this study")
            except Study.DoesNotExist:
                raise Http404("Study not found")

        user = self.request.user
        
        # Superuser sees everything
        if user.is_superuser:
            return queryset

        # Complex permission logic with updated role fields
        filters = models.Q(study__security_level=SecurityLevel.PUBLIC)
        
        if user.is_authenticated:
            if user.is_staff:
                filters |= models.Q(study__security_level=SecurityLevel.INTERNAL)
            
            # User-specific access - adapt to use guardian permissions
            visible_assays = []
            for assay in queryset:
                if assay.study.can_read(user):
                    visible_assays.append(assay.id)
                    
            if visible_assays:
                filters |= models.Q(id__in=visible_assays)

        return queryset.filter(filters).distinct()

    def get_object(self):
        try:
            # First check investigation and study if in nested routes
            investigation_accession = self.kwargs.get('investigation_accession_code')
            study_accession = self.kwargs.get('study_accession_code')
            
            if investigation_accession:
                try:
                    investigation = Investigation.objects.get(accession_code=investigation_accession)
                except Investigation.DoesNotExist:
                    raise Http404("Investigation not found")
            
            if study_accession:
                try:
                    study = Study.objects.get(accession_code=study_accession)
                except Study.DoesNotExist:
                    raise Http404("Study not found")

            # Then try to get the assay
            assay = Assay.objects.get(
                accession_code=self.kwargs[self.lookup_field]
            )
            
            # Check investigation and study if in nested routes
            if investigation_accession:
                if assay.study.investigation.accession_code != investigation_accession:
                    raise Http404("Assay does not belong to the specified investigation")
            
            if study_accession:
                if assay.study.accession_code != study_accession:
                    raise Http404("Assay does not belong to the specified study")
            
            # Check permissions
            if not assay.study.can_read(self.request.user):
                raise PermissionDenied("You do not have permission to access this assay")
                
            return assay
            
        except Assay.DoesNotExist:
            raise Http404("Assay not found")


class UserRoleManagementViewSet(viewsets.ViewSet):
    permission_classes = [IsOwnerOrAdmin]
    
    @action(detail=True, methods=['post'], url_path='assign-investigation-role')
    def assign_investigation_role(self, request, pk=None):
        """
        Assign a role to a user for an investigation.
        POST data should include:
        - user_id: The ID of the user to assign the role to
        - role: One of 'viewer', 'contributor', 'owner'
        """
        try:
            investigation = Investigation.objects.get(pk=pk)
            self.check_object_permissions(request, investigation)
            
            user_id = request.data.get('user_id')
            role = request.data.get('role')
            
            if not user_id or not role:
                return Response(
                    {'error': 'Both user_id and role are required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if role not in [UserRole.VIEWER, UserRole.CONTRIBUTOR, UserRole.OWNER]:
                return Response(
                    {'error': f'Role must be one of: {UserRole.VIEWER}, {UserRole.CONTRIBUTOR}, {UserRole.OWNER}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
            investigation.assign_role(user, role)
            return Response({'status': 'success'})
            
        except Investigation.DoesNotExist:
            return Response(
                {'error': 'Investigation not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], url_path='remove-investigation-user')
    def remove_investigation_user(self, request, pk=None):
        """
        Remove a user's permissions from an investigation.
        POST data should include:
        - user_id: The ID of the user to remove
        """
        try:
            investigation = Investigation.objects.get(pk=pk)
            self.check_object_permissions(request, investigation)
            
            user_id = request.data.get('user_id')
            
            if not user_id:
                return Response(
                    {'error': 'user_id is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
            try:
                investigation.remove_user(user)
                return Response({'status': 'success'})
            except ValidationError as e:
                return Response(
                    {'error': 'Internal server error'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Investigation.DoesNotExist:
            return Response(
                {'error': 'Investigation not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], url_path='assign-study-role')
    def assign_study_role(self, request, pk=None):
        """
        Assign a role to a user for a study.
        POST data should include:
        - user_id: The ID of the user to assign the role to
        - role: One of 'viewer', 'contributor', 'owner'
        """
        try:
            study = Study.objects.get(pk=pk)
            self.check_object_permissions(request, study)
            
            user_id = request.data.get('user_id')
            role = request.data.get('role')
            
            if not user_id or not role:
                return Response(
                    {'error': 'Both user_id and role are required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if role not in [UserRole.VIEWER, UserRole.CONTRIBUTOR, UserRole.OWNER]:
                return Response(
                    {'error': f'Role must be one of: {UserRole.VIEWER}, {UserRole.CONTRIBUTOR}, {UserRole.OWNER}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
            study.assign_role(user, role)
            return Response({'status': 'success'})
            
        except Study.DoesNotExist:
            return Response(
                {'error': 'Study not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='list-study-permissions')
    def list_study_permissions(self, request, pk=None):
        """
        List all user permissions for a study.
        """
        try:
            study = Study.objects.get(pk=pk)
            
            # Check if user has access to see permissions
            if not study.can_read(request.user):
                raise PermissionDenied("You don't have permission to view this study's permissions")
                
            # Use guardian's get_users_with_perms instead of StudyPermission
            users_with_perms = get_users_with_perms(study, attach_perms=True)
            
            # Format the response
            permission_data = []
            for user, perms in users_with_perms.items():
                # Get the user's role
                role = study.get_user_role(user)
                
                permission_data.append({
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': role,
                    'permissions': list(perms)
                })
                
            return Response(permission_data)
            
        except Study.DoesNotExist:
            return Response(
                {'error': 'Study not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        except Exception as e:
            return Response(
                {'error': 'Internal server error'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SampleViewSet(viewsets.ModelViewSet):
    queryset = Sample.objects.all()
    serializer_class = SampleSerializer
    permission_classes = [GuardianPermission]  # Add permission class
    lookup_field = 'accession_code'
    lookup_value_regex = 'CXRX[0-9]+'
    
    # Add filtering based on visibility
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # Filter based on permissions
        visible_objects = [obj for obj in queryset if obj.is_visible(user)]
        return self.queryset.model.objects.filter(pk__in=[obj.pk for obj in visible_objects])