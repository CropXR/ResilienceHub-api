# api/v2/views.py
import json

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Model
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.template import loader
from guardian.core import ObjectPermissionChecker
from guardian.shortcuts import assign_perm
from guardian.shortcuts import remove_perm, get_perms, get_users_with_perms
from metadata_template_generator.generate_excel_template.appendix_sheet import create_section_appendix_sheet
from metadata_template_generator.generate_excel_template.format import get_default_conditional_formatting, \
    get_default_number_formatting, format_workbook
from metadata_template_generator.generate_excel_template.section_sheet import create_section_sheet
from metadata_template_generator.generate_excel_template.template_generator import generate_template, get_template_name, \
    sort_sections, create_overview_sheet
from metadata_template_generator.parser import parse_schema, read_values_from_template
from openpyxl.styles.builtins import title
from openpyxl.workbook import Workbook
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    InvestigationSerializer,
    StudySerializer,
    AssaySerializer,
    SampleSerializer
)
from ..models import (
    Investigation, Study, Assay,
    SecurityLevel,
    Sample, Institution, InvestigationInstitution
)
from ..permissions import GuardianPermission, IsOwnerOrAdmin
from ..permissions import (
    ROLE_PERMISSIONS
)

# Define guardian permission codenames
VIEW_PERMISSION = 'view_{model}'
CHANGE_PERMISSION = 'change_{model}'
DELETE_PERMISSION = 'delete_{model}'
MANAGE_PERMISSION = 'manage_permissions_{model}'

# Define the role to permission mapping
ROLE_PERMISSIONS = {
    'authorized': [VIEW_PERMISSION],
    'contributor': [VIEW_PERMISSION, CHANGE_PERMISSION],
    'owner': [VIEW_PERMISSION, CHANGE_PERMISSION, DELETE_PERMISSION, MANAGE_PERMISSION],
}


def metadata_templates_page(request) -> Response:
    template = loader.get_template('metadata_template_upload.html')
    return HttpResponse(template.render({}, request))


def sequencing_template_download(request) -> Response:
    metadata_type = "sequencing"
    return _return_template(metadata_type)


def phenotyping_template_download(request) -> Response:
    metadata_type = "phenotyping"
    return _return_template(metadata_type)


def _return_template(metadata_type: str) -> Response:
    schema = parse_schema(metadata_type)
    file_name = get_template_name(metadata_type, schema.version)
    wb = _generate_template(schema, metadata_type)
    response = HttpResponse(wb, content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename={file_name}'
    return response


def _generate_template(schema, metadata_type) -> Workbook:
    wb = Workbook()
    sections = sort_sections(schema.sections, metadata_type)
    create_overview_sheet(sections, wb, schema.version)
    for section in sections:
        create_section_sheet(
            section, wb,
            conditional_formatting=get_default_conditional_formatting(metadata_type),
            number_formatting=get_default_number_formatting(metadata_type)
        )
        create_section_appendix_sheet(section, wb)
    format_workbook(wb)
    return wb


def ingest_metadata_template(request) -> Response:
    print(request)
    if request.method == "POST" and (file := request.FILES['file']):
        metadata_type = request.POST['metadata_type']
        save_data_from_uploaded_metadata_template_to_db(request.FILES["file"], metadata_type, request.user)
        return HttpResponse("Form is valid")
    else:
        return HttpResponse("Failed to upload")


def save_data_from_uploaded_metadata_template_to_db(file, metadata_type: str, user):
    file_name = 'ingested_file.xlsx'
    with open(file_name, "wb+") as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    values = read_values_from_template(
        metadata_type, file_name, include_new_columns=True
    )
    investigation = Investigation(
        title=values['investigation'][0]['investigation_title'],
        description=values['investigation'][0]['investigation_description']
    )
    investigation.save()
    set_owner_permission(investigation, 'investigation', user)
    institution = Institution(
        name=values['institution'][0]['organisation']
    )
    institution.save()
    investitition = InvestigationInstitution(project=investigation, institution=institution)
    investitition.save()


def set_owner_permission(model: Model, model_name: str, user):
    # Get the content type for Investigation
    content_type = ContentType.objects.get_for_model(model)

    # Ensure permissions exist before assigning
    for perm_type in ROLE_PERMISSIONS['owner']:
        # Construct the full permission codename
        codename = f'{perm_type}_{model_name}'

        # Create the permission if it doesn't exist
        Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={'name': f'Can {perm_type} {model_name}'}
        )

        # Assign the permission
        assign_perm(codename, user, model)

    # Store role information
    model.set_user_role(user, 'owner')


class InvestigationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, GuardianPermission]
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
            
            # Check permissions using guardian
            if not self.request.user.has_perm('api.view_investigation', investigation):
                raise PermissionDenied
                
            return investigation
            
        except Investigation.DoesNotExist:
            raise Http404

    def get_queryset(self):
        user = self.request.user
        base_queryset = Investigation.objects.all()

        # Superuser sees everything
        if user.is_superuser:
            return base_queryset

        # Use guardian's ObjectPermissionChecker for efficient permission checks
        checker = ObjectPermissionChecker(user)
        checker.prefetch_perms(base_queryset)
        
        # Filter based on guardian permissions
        visible_ids = [
            inv.id for inv in base_queryset
            if checker.has_perm('api.view_investigation', inv) and
            # Apply confidentiality filtering
            (inv.security_level != SecurityLevel.CONFIDENTIAL or 
             user.has_perm('api.view_investigation', inv))
        ]
        
        return base_queryset.filter(id__in=visible_ids).order_by('id')
    
    def perform_create(self, serializer):
        # Set the current user as owner when creating a new investigation
        investigation = serializer.save()
        set_owner_permission(investigation, 'investigation', self.request.user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        self.check_object_permissions(request, instance)
        return super().update(request, *args, **kwargs)

class StudyViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, GuardianPermission]
    queryset = Study.objects.all()
    serializer_class = StudySerializer
    lookup_field = 'accession_code'
    lookup_value_regex = 'CXRS[0-9]+'

    def get_queryset(self):
        queryset = Study.objects.all()
        
        # Filter by investigation
        investigation_id = self.request.query_params.get('investigation', None)
        investigation_accession = self.request.query_params.get('investigation_accession', None)
        
        if investigation_id:
            queryset = queryset.filter(investigation_id=investigation_id)
        
        if investigation_accession:
            queryset = queryset.filter(investigation__accession_code=investigation_accession)
        
        # Additional optional filters
        title = self.request.query_params.get('title', None)
        description = self.request.query_params.get('description', None)
        security_level = self.request.query_params.get('security_level', None)
        
        if title:
            queryset = queryset.filter(title__icontains=title)
        
        if description:
            queryset = queryset.filter(description__icontains=description)
        
        if security_level:
            queryset = queryset.filter(security_level=security_level)

        # Permission filtering using guardian
        user = self.request.user
        
        # Superuser sees everything
        if user.is_superuser:
            return queryset

        # Use guardian's ObjectPermissionChecker for efficient permission checks
        checker = ObjectPermissionChecker(user)
        checker.prefetch_perms(queryset)
        
        # Filter based on permissions and security level
        visible_ids = []
        for study in queryset:
            # Public studies are visible to all
            if study.security_level == SecurityLevel.PUBLIC:
                visible_ids.append(study.id)
                continue
                
            # Check guardian permissions
            if checker.has_perm('api.view_study', study):
                # For confidential studies, only show if explicitly allowed
                if study.security_level != SecurityLevel.CONFIDENTIAL or checker.has_perm('api.view_study', study):
                    visible_ids.append(study.id)
                    continue
                    
            # Check investigation-level access
            if study.investigation and checker.has_perm('api.view_investigation', study.investigation):
                # Internal users can see internal studies in investigations they can view
                if study.security_level == SecurityLevel.INTERNAL and user.is_staff:
                    visible_ids.append(study.id)
                    continue
                
                # Investigation-level permissions for contributors and owners
                if checker.has_perm('api.change_investigation', study.investigation):
                    visible_ids.append(study.id)
                    continue

        return queryset.filter(id__in=visible_ids).distinct()

    def get_object(self):
        try:
            # First check investigation if in nested route
            investigation_accession = self.kwargs.get('investigation_accession_code')
            if investigation_accession:
                try:
                    investigation = Investigation.objects.get(accession_code=investigation_accession)
                except Investigation.DoesNotExist:
                    raise Http404("Investigation not found")

            # Then try to get the study
            study = Study.objects.get(
                accession_code=self.kwargs[self.lookup_field]
            )
            
            # Check investigation if in nested route
            if investigation_accession:
                if study.investigation.accession_code != investigation_accession:
                    raise Http404("Study does not belong to the specified investigation")
            
            # Check permissions using guardian
            if not self.request.user.has_perm('api.view_study', study):
                # Check investigation-level permission as fallback
                if not (study.investigation and 
                        self.request.user.has_perm('api.view_investigation', study.investigation)):
                    raise PermissionDenied("You do not have permission to access this study")
                
            return study
            
        except Study.DoesNotExist:
            raise Http404("Study not found")
            
    def perform_create(self, serializer):
        # Set the current user as owner when creating a new study
        study = serializer.save()
        set_owner_permission(study, 'study', self.request.user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        self.check_object_permissions(request, instance)
        return super().update(request, *args, **kwargs)

class AssayViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, GuardianPermission]
    serializer_class = AssaySerializer
    lookup_field = 'accession_code'
    lookup_value_regex = 'CXRA[0-9]+'

    def get_queryset(self):
        queryset = Assay.objects.all()
        
        # Filter by investigation
        investigation_id = self.request.query_params.get('investigation', None)
        investigation_accession = self.request.query_params.get('investigation_accession', None)
        
        # Filter by study
        study_id = self.request.query_params.get('study', None)
        study_accession = self.request.query_params.get('study_accession', None)
        
        if investigation_id:
            queryset = queryset.filter(study__investigation_id=investigation_id)
        
        if investigation_accession:
            queryset = queryset.filter(study__investigation__accession_code=investigation_accession)
        
        if study_id:
            queryset = queryset.filter(study_id=study_id)
        
        if study_accession:
            queryset = queryset.filter(study__accession_code=study_accession)
        
        # Additional optional filters
        title = self.request.query_params.get('title', None)
        description = self.request.query_params.get('description', None)
        measurement_type = self.request.query_params.get('measurement_type', None)
        technology_platform = self.request.query_params.get('technology_platform', None)
        
        if title:
            queryset = queryset.filter(title__icontains=title)
        
        if description:
            queryset = queryset.filter(description__icontains=description)
        
        if measurement_type:
            queryset = queryset.filter(measurement_type=measurement_type)
        
        if technology_platform:
            queryset = queryset.filter(technology_platform=technology_platform)

        # Permission filtering using guardian
        user = self.request.user
        
        # Superuser sees everything
        if user.is_superuser:
            return queryset

        # Prefetch studies for permission checking
        studies = set(assay.study for assay in queryset)
        
        # Use guardian's ObjectPermissionChecker for efficient permission checks
        checker = ObjectPermissionChecker(user)
        checker.prefetch_perms(studies)
        
        # Filter based on study permissions
        visible_ids = []
        for assay in queryset:
            study = assay.study
            
            # Public studies' assays are visible to all
            if study.security_level == SecurityLevel.PUBLIC:
                visible_ids.append(assay.id)
                continue
                
            # Check study permissions
            if checker.has_perm('api.view_study', study):
                # For confidential studies, only show if explicitly allowed
                if study.security_level != SecurityLevel.CONFIDENTIAL or checker.has_perm('api.view_study', study):
                    visible_ids.append(assay.id)
                    continue
                    
            # Check investigation-level access
            if study.investigation and checker.has_perm('api.view_investigation', study.investigation):
                # Internal users can see internal studies' assays
                if study.security_level == SecurityLevel.INTERNAL and user.is_staff:
                    visible_ids.append(assay.id)
                    continue
                
                # Investigation-level permissions for contributors and owners
                if checker.has_perm('api.change_investigation', study.investigation):
                    visible_ids.append(assay.id)
                    continue

        return queryset.filter(id__in=visible_ids).distinct()

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
            
            # Check permissions using guardian for the parent study
            if not self.request.user.has_perm('api.view_study', assay.study):
                # Check investigation-level permission as fallback
                if not (assay.study.investigation and 
                        self.request.user.has_perm('api.view_investigation', assay.study.investigation)):
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
        - role: One of 'authorized', 'contributor', 'owner'
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
            
            # Validate role
            if role not in ['authorized', 'contributor', 'owner']:
                return Response(
                    {'error': f'Role must be one of: authorized, contributor, owner'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
                
            # First remove existing permissions
            for perm in get_perms(user, investigation):
                remove_perm(perm, user, investigation)
                
            # Assign new permissions based on role
            model_name = 'investigation'
            for perm_pattern in ROLE_PERMISSIONS[role]:
                perm = f'api.{perm_pattern.format(model=model_name)}'
                assign_perm(perm, user, investigation)
            
            # Store role information
            investigation.set_user_role(user, role)
            
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
                # Check if user is the last owner
                if investigation.get_user_role(user) == 'owner':
                    owners = [u for u in get_users_with_perms(investigation) 
                             if investigation.get_user_role(u) == 'owner']
                    if len(owners) <= 1:
                        return Response(
                            {'error': 'Cannot remove the last owner. Assign another owner first.'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                
                # Remove all permissions
                for perm in get_perms(user, investigation):
                    remove_perm(perm, user, investigation)
                
                # Clear role information
                investigation.clear_user_role(user)
                
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
        - role: One of 'authorized', 'contributor', 'owner'
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
            
            if role not in ['authorized', 'contributor', 'owner']:
                return Response(
                    {'error': f'Role must be one of: authorized, contributor, owner'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # First remove existing permissions
            for perm in get_perms(user, study):
                remove_perm(perm, user, study)
            
            # Assign new permissions based on role
            model_name = 'study'
            for perm_pattern in ROLE_PERMISSIONS[role]:
                perm = f'api.{perm_pattern.format(model=model_name)}'
                assign_perm(perm, user, study)
            
            # Store role information
            study.set_user_role(user, role)
            
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
            if not self.request.user.has_perm('api.view_study', study):
                raise PermissionDenied("You don't have permission to view this study's permissions")
                
            # Get all users with permissions on this study
            users_with_perms = get_users_with_perms(
                study, 
                attach_perms=True,
                with_superusers=True
            )
            
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
    permission_classes = [IsAuthenticated, GuardianPermission]
    lookup_field = 'accession_code'
    lookup_value_regex = 'CXRX[0-9]+'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Superuser sees everything
        if user.is_superuser:
            return queryset
            
        # Use guardian's ObjectPermissionChecker for efficient permission checks
        checker = ObjectPermissionChecker(user)
        checker.prefetch_perms(queryset)
        
        # Filter based on permissions and visibility
        visible_ids = []
        for sample in queryset:
            # Public samples are visible to all
            if sample.security_level == SecurityLevel.PUBLIC:
                visible_ids.append(sample.id)
                continue
                
            # Skip confidential in listings unless explicitly permitted
            if sample.security_level == SecurityLevel.CONFIDENTIAL:
                if checker.has_perm('api.view_sample', sample):
                    visible_ids.append(sample.id)
                continue
                
            # Check internal access
            if sample.security_level == SecurityLevel.INTERNAL:
                if user.is_staff or checker.has_perm('api.view_sample', sample):
                    visible_ids.append(sample.id)
                continue
                
            # Check restricted access
            if sample.security_level == SecurityLevel.RESTRICTED:
                if checker.has_perm('api.view_sample', sample):
                    visible_ids.append(sample.id)
                continue
                
        return queryset.filter(id__in=visible_ids)
    
    
class ISAExportView(APIView):
    """
    View to export the ISA structure as a JSON representation that can be
    used to generate a folder structure for data organization.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, code=None):
        """
        Handle GET request for ISA export.
        The 'code' parameter can be either an ID or an accession code.
        """
        if not code:
            return Response(
                {"error": "Investigation ID or accession code required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Remove any trailing slashes from the code
        code = code.rstrip('/')
        
        # Try to get the investigation by ID or accession code
        investigation = None
        
        # Try a few different patterns for the accession code
        possible_codes = [
            code.upper(),                    # Original code (uppercase)
            code.upper().replace('CRXP', 'CXRP'),  # Fix common typo CRXP -> CXRP
            'CXRP' + code if code.isdigit() else code  # Add prefix if it's just a number
        ]
        
        # Try each possible accession code
        for possible_code in possible_codes:
            if possible_code.startswith('CXRP'):
                try:
                    investigation = Investigation.objects.get(accession_code=possible_code)
                    break  # Found it, exit the loop
                except Investigation.DoesNotExist:
                    continue
        
        # If not found by accession code, try as numeric ID
        if investigation is None:
            try:
                id_value = int(code)
                investigation = Investigation.objects.get(id=id_value)
            except (ValueError, Investigation.DoesNotExist):
                pass
        
        # If still not found, return error with diagnostic info
        if investigation is None:
            # Get a list of all available accession codes for debugging
            available_codes = list(Investigation.objects.values_list('accession_code', flat=True))
            return Response(
                {
                    "error": f"Investigation not found with ID or accession code: {code}",
                    "debug_info": {
                        "tried_codes": possible_codes,
                        "available_codes": available_codes[:10]  # Show first 10 for debugging
                    }
                }, 
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Check if user has permission to access the investigation
        if not investigation._check_security_level_read(request.user):
            return Response(
                {"error": "You do not have permission to access this investigation"}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Generate the ISA structure
        isa_structure = self.generate_isa_structure(investigation, request)
        
        return Response(isa_structure)
    
    def generate_isa_structure(self, investigation, request):
        """
        Generate the ISA structure for the given investigation.
        
        Args:
            investigation: The investigation model instance
            request: The HTTP request object
        """
        # Format directory name for investigation
        i_dir_name = f"i_{investigation.accession_code}"
        
        # Create the base structure with minimal README content
        isa_structure = {
            i_dir_name: {
                "_readme": f"# Investigation: {investigation.accession_code}\n\n{investigation.title}\n\n**DO NOT MODIFY THIS FILE MANUALLY**",
                "investigation.json": self.generate_investigation_json(investigation)
            }
        }
        
        # Add studies to the structure
        studies = Study.objects.filter(investigation=investigation)
        
        for study in studies:
            # Only include studies the user can access
            if study._check_security_level_read(request.user):
                s_dir_name = f"s_{investigation.accession_code}-{study.accession_code}"
                
                # Add study directory to structure
                isa_structure[i_dir_name][s_dir_name] = self.generate_study_structure(investigation, study, request)
        
        return isa_structure
    
    def generate_investigation_json(self, investigation):
        """Generate the investigation.json content."""
        # Create studies list for the investigation
        studies = Study.objects.filter(investigation=investigation)
        study_list = []
        
        for study in studies:
            s_dir_name = f"s_{investigation.accession_code}-{study.accession_code}__{study.slug}"

            study_list.append({
                "study_id": s_dir_name,
                "study_title": study.title
            })
        
        investigation_data = {
            "investigation_id": investigation.accession_code,
            "investigation_title": investigation.title,
            "investigation_description": investigation.description,
            "investigation_submission_date": investigation.submission_date.isoformat() if investigation.submission_date else "",
            "investigation_public_release_date": investigation.public_release_date.isoformat() if investigation.public_release_date else "",
            "investigation_security_level": investigation.security_level,
            "studies": study_list
        }
        
        return json.dumps(investigation_data, indent=2)
    
    def generate_study_structure(self, investigation, study, request):
        """
        Generate the structure for a study directory.
        
        Args:
            investigation: The investigation model instance
            study: The study model instance
            request: The HTTP request object
        """
        study_structure = {
            "_readme": f"# Study: {study.accession_code}\n\n{study.title}\n\n**DO NOT MODIFY THIS FILE MANUALLY**",
            "study.json": self.generate_study_json(investigation, study)
        }
        
        # Add assays to the structure
        assays = Assay.objects.filter(study=study)
        for assay in assays:
            a_dir_name = f"a_{investigation.accession_code}-{study.accession_code}-{assay.accession_code}"
            study_structure[a_dir_name] = self.generate_assay_structure(investigation, study, assay)
        
        return study_structure
    
    def generate_study_json(self, investigation, study):
        """Generate the study.json content with actual study data."""
                
        study_data = {
            "study_id": study.accession_code,
            "study_title": study.title,
            "study_security_level": study.security_level,
            "study_description": study.description or "",
            "study_submission_date": study.submission_date.isoformat() if study.submission_date else "",
            "study_public_release_date": study.public_release_date.isoformat() if study.public_release_date else "",
        }
        
        return json.dumps(study_data, indent=2)
    
    def generate_assay_structure(self, investigation, study, assay):
        """Generate the structure for an assay directory."""
        assay_structure = {
            "_readme": f"# Assay: {assay.accession_code}\n\n{assay.title}\n\n**DO NOT MODIFY THIS FILE MANUALLY**",
            "assay.json": self.generate_assay_json(investigation, study, assay)
        }
        
        # Add minimal directory structures for data organization
        assay_structure["raw-data"] = {
            "_readme": "# Raw Data\n\nPlace raw data files here.\n\n**DO NOT MODIFY THIS FILE MANUALLY**"
        }
        
        assay_structure["processed"] = {
            "_readme": "# Processed Data\n\nPlace processed data files here.\n\n**DO NOT MODIFY THIS FILE MANUALLY**"
        }
        
        return assay_structure
    
    def generate_assay_json(self, investigation, study, assay):
        """Generate the assay.json content with actual assay data."""
        a_dir_name = f"a_{investigation.accession_code}-{study.accession_code}-{assay.accession_code}"
        
        assay_data = {
            "assay_id": assay.accession_code,
            "assay_title": assay.title,
            "assay_measurement_type": assay.measurement_type,
            "assay_technology_platform": assay.technology_platform,
            "assay_description": assay.description
        }
        
        return json.dumps(assay_data, indent=2)
    
    
    