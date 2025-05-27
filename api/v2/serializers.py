# isa_api/v1/serializers.py
from typing import List

from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema_serializer, extend_schema_field
from rest_framework import serializers

from ..database_models.models import Institution, Investigation, Study, Assay, Sample


@extend_schema_serializer(component_name="UserV1")
class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        full_name = obj.get_full_name() or obj.username
        return f"{full_name} ({obj.email})"

    class Meta:
        model = User
        fields = ['display_name']

@extend_schema_serializer(component_name="InvestigationV2")
class InvestigationSerializer(serializers.ModelSerializer):
    studies = serializers.SerializerMethodField()
    owners = serializers.SerializerMethodField()
    contributors = serializers.SerializerMethodField()
    readers = serializers.SerializerMethodField()
    
    # Add this if it's a many-to-many or foreign key relationship
    participating_institutions = serializers.PrimaryKeyRelatedField(
        queryset=Institution.objects.all(),  # Replace with your actual model
        many=True,  # Set to False if it's a ForeignKey rather than ManyToMany
        required=False
    )

    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    submission_date = serializers.DateField(required=False)
    public_release_date = serializers.DateField(required=False)
    
    class Meta:
        model = Investigation
        fields = [
            'accession_code',
            'security_level',
            'title', 
            'description', 
            'principal_investigator_name',
            'principal_investigator_email',
            'start_date',
            'end_date',
            'submission_date',
            'public_release_date', 
            'studies',
            'owners',
            'contributors',
            'readers',
            'participating_institutions'
        ]
        read_only_fields = ['accession_code', 'created_at', 'updated_at']

    @extend_schema_field({'type': 'array', 'items': {'type': 'array', 'items': {'type': 'string'}}})
    def get_studies(self, obj) -> List[List[str]]:
        """Get studies filtered by user permissions"""
        user = self.context['request'].user
        
        filtered_studies = []
        studies = obj.studies.all()
        
        for study in studies:
            if study.can_read(user):
                filtered_studies.append([study.accession_code, study.title])

        return filtered_studies
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_owners(self, obj) -> List[str]:
        """Get owners of the investigation"""
        owners = obj.get_users_by_role('owner')
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in owners
        ]
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_contributors(self, obj) -> List[str]:
        """Get contributors of the investigation"""
        contributors = obj.get_users_by_role('contributor')
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in contributors
        ]
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_readers(self, obj) -> List[str]:
        """Get readers of the investigation"""
        readers = obj.get_users_by_role('viewer')
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in readers
        ]

@extend_schema_serializer(component_name="StudyV2")
class StudySerializer(serializers.ModelSerializer):
    assays = serializers.SerializerMethodField()
    owners = serializers.SerializerMethodField()
    contributors = serializers.SerializerMethodField()
    readers = serializers.SerializerMethodField()
        
    investigation = serializers.PrimaryKeyRelatedField(
        queryset=Investigation.objects.all(),
        required=False,
        write_only=True
    )
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        user = self.context.get('request').user if self.context.get('request') else None
        
        if user:
            # Start with all investigations
            accessible_investigations = Investigation.objects.all()
            
            # For confidential investigations, filter by read access
            if not user.is_superuser:  # Skip filtering for superusers
                confidential_ids = Investigation.objects.filter(
                    security_level=SecurityLevel.CONFIDENTIAL
                ).values_list('id', flat=True)
                
                # Exclude confidential investigations that the user can't read
                confidential_without_access = []
                for inv_id in confidential_ids:
                    inv = Investigation.objects.get(id=inv_id)
                    if not inv.can_read(user):
                        confidential_without_access.append(inv_id)
                
                # Exclude the confidential investigations without access
                accessible_investigations = accessible_investigations.exclude(
                    id__in=confidential_without_access
                )
            
            self.fields['investigation'].queryset = accessible_investigations

    def create(self, validated_data):
        # If investigation is not in validated_data, try to get it from context
        if 'investigation' not in validated_data:
            request = self.context.get('request')
            if request:
                # Check for investigation in nested route
                investigation_accession = request.parser_context['kwargs'].get('investigation_accession_code')
                if investigation_accession:
                    try:
                        investigation = Investigation.objects.get(accession_code=investigation_accession)
                        validated_data['investigation'] = investigation
                    except Investigation.DoesNotExist:
                        raise serializers.ValidationError({"investigation": "Invalid investigation specified."})
        
        # If still no investigation, raise an error
        if 'investigation' not in validated_data:
            raise serializers.ValidationError({"investigation": "This field is required."})
        
        # Set the current user as owner when creating
        study = super().create(validated_data)
        study.set_user_role(self.context['request'].user, 'owner')
        
        return study

    class Meta:
        model = Study
        fields = [
            'accession_code',
            'investigation',
            'title',
            'slug',
            'description',
            'principal_investigator_name',
            'principal_investigator_email',
            'submission_date', 
            'assays',
            'security_level',
            'owners',
            'contributors',
            'readers',
            'folder_name'
        ]
        read_only_fields = ['accession_code', 'investigation']

    @extend_schema_field({'type': 'array', 'items': {'type': 'array', 'items': {'type': 'string'}}})
    def get_assays(self, obj) -> List[List[str]]:
        """Get assays filtered by user permissions"""
        user = self.context['request'].user
        return [
            [assay.accession_code, assay.measurement_type]
            for assay in obj.assays.all() if assay.can_read(user)
        ]
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_owners(self, obj) -> List[str]:
        """Get owners of the study"""
        owners = obj.get_users_by_role('owner')
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in owners
        ]
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_contributors(self, obj) -> List[str]:
        """Get contributors of the study"""
        contributors = obj.get_users_by_role('contributor')
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in contributors
        ]
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_readers(self, obj) -> List[str]:
        """Get readers of the study"""
        readers = obj.get_users_by_role('authorized')
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in readers
        ]

@extend_schema_serializer(component_name="AssayV2")
class AssaySerializer(serializers.ModelSerializer):
    study = serializers.PrimaryKeyRelatedField(
        queryset=Study.objects.all(),
        required=False,
        write_only=True
    )
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        user = self.context.get('request').user if self.context.get('request') else None
        
        if user:
            # Start with all studies
            accessible_studies = Study.objects.all()
            
            # For confidential studies, filter by read access
            if not user.is_superuser:  # Skip filtering for superusers
                confidential_ids = Study.objects.filter(
                    security_level=SecurityLevel.CONFIDENTIAL
                ).values_list('id', flat=True)
                
                # Exclude confidential studies that the user can't read
                confidential_without_access = []
                for study_id in confidential_ids:
                    study = Study.objects.get(id=study_id)
                    if not study.can_read(user):
                        confidential_without_access.append(study_id)
                
                # Exclude the confidential studies without access
                accessible_studies = accessible_studies.exclude(
                    id__in=confidential_without_access
                )
            
            self.fields['study'].queryset = accessible_studies

    def create(self, validated_data):
        # If study is not in validated_data, try to get it from context
        if 'study' not in validated_data:
            request = self.context.get('request')
            if request:
                # Check for study in nested route
                study_accession = request.parser_context['kwargs'].get('study_accession_code')
                investigation_accession = request.parser_context['kwargs'].get('investigation_accession_code')
                
                if study_accession:
                    try:
                        study = Study.objects.get(accession_code=study_accession)
                        validated_data['study'] = study
                    except Study.DoesNotExist:
                        raise serializers.ValidationError({"study": f"Study with accession code {study_accession} does not exist"})
                
                elif investigation_accession:
                    # If no specific study, but investigation is provided
                    try:
                        investigation = Investigation.objects.get(accession_code=investigation_accession)
                        # You might want to add logic to select a specific study or create one
                        raise serializers.ValidationError({"study": "A specific study must be provided"})
                    except Investigation.DoesNotExist:
                        raise serializers.ValidationError({"investigation": "Invalid investigation specified."})
        
        # If still no study, raise an error
        if 'study' not in validated_data:
            raise serializers.ValidationError({"study": "This field is required."})
        
        # Set the current user as owner when creating
        assay = super().create(validated_data)
        assay.set_user_role(self.context['request'].user, 'owner')
        
        return assay

    class Meta:
        model = Assay
        fields = [
            'accession_code',
            'study',
            'title',
            'description',
            'measurement_type',
            'technology_platform',
            # Add other fields as needed
        ]
        read_only_fields = ['accession_code', 'study']
    
@extend_schema_serializer(component_name="SampleV2")
class SampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sample
        fields = [
            'accession_code', 
            'sample_type'
        ]
        read_only_fields = ['accession_code']