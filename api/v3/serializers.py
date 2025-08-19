# isa_api/v1/serializers.py
from rest_framework import serializers
from typing import List, Dict, Any
from drf_spectacular.types import OpenApiTypes

from django.contrib.auth.models import User
from ..models import (
    Investigation, 
    Study, 
    SecurityLevel, 
    Institution,
)
from drf_spectacular.utils import extend_schema_serializer, extend_schema_field


@extend_schema_serializer(component_name="UserV3")
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


@extend_schema_serializer(component_name="InvestigationV3")
class InvestigationSerializer(serializers.ModelSerializer):
    studies = serializers.SerializerMethodField()
    principal_investigator = UserSerializer(read_only=True)
    
    class Meta:
        model = Investigation
        fields = [
            'accession_code',
            'work_package',
            'title', 
            'security_level',
            'description', 
            'principal_investigator',
            'studies',
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
    
@extend_schema_serializer(component_name="StudyV3")
class StudySerializer(serializers.ModelSerializer):
    
    # Investigation fields that should be inherited if not set on study
    investigation_title = serializers.SerializerMethodField()
    investigation_accession_code = serializers.SerializerMethodField()
    investigation_work_package = serializers.SerializerMethodField()
    principal_investigator = serializers.SerializerMethodField()
    dataset_administrator = serializers.SerializerMethodField()
        
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
            'security_level',
            'investigation',
            'investigation_title',
            'investigation_accession_code',
            'investigation_work_package',
            'principal_investigator',
            'dataset_administrator',
            'title',
            'slug',
            'description',
        ]
        read_only_fields = ['accession_code', 'investigation']

    @extend_schema_field({'type': 'string'})
    def get_investigation_title(self, obj) -> str:
        """Get the parent investigation title"""
        return obj.investigation.title if obj.investigation else ""
    
    @extend_schema_field({'type': 'string'})
    def get_investigation_description(self, obj) -> str:
        """Get the parent investigation description"""
        return obj.investigation.description if obj.investigation else ""
    
    @extend_schema_field({'type': 'string'})
    def get_investigation_accession_code(self, obj) -> str:
        """Get the parent investigation accession code"""
        return obj.investigation.accession_code if obj.investigation else ""

    @extend_schema_field({'type': 'string'})
    def get_investigation_work_package(self, obj) -> str:
        """Get the parent investigation work package"""
        return obj.investigation.work_package if obj.investigation else ""
    
    @extend_schema_field({'type': 'object', 'properties': {'first_name': {'type': 'string'}, 'last_name': {'type': 'string'}, 'email': {'type': 'string'}}})
    def get_principal_investigator(self, obj) -> dict:
        """Get principal investigator from parent investigation"""
        if obj.investigation and obj.investigation.principal_investigator:
            user = obj.investigation.principal_investigator
            return {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email
            }
        return None
    
    @extend_schema_field({'type': 'object', 'properties': {'first_name': {'type': 'string'}, 'last_name': {'type': 'string'}, 'email': {'type': 'string'}}})
    def get_dataset_administrator(self, obj) -> dict:
        """Get data administrator from parent investigation"""
        if obj.dataset_administrator:
            user = obj.dataset_administrator
            return {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email
            }
        return None
    
    @extend_schema_field({'type': 'string'})
    def get_investigation_notes(self, obj) -> str:
        """Get the parent investigation notes"""
        return obj.investigation.notes if obj.investigation else ""
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'object', 'properties': {'id': {'type': 'integer'}, 'name': {'type': 'string'}}}})
    def get_investigation_participating_institutions(self, obj) -> List[Dict[str, Any]]:
        """Get the parent investigation participating institutions"""
        if not obj.investigation:
            return []
        return [
            {
                'id': institution.id,
                'name': institution.name,
                'website': institution.website,
                'address_country': str(institution.address_country) if institution.address_country else None
            }
            for institution in obj.investigation.participating_institutions.all()
        ]

    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_owners(self, obj) -> List[str]:
        """Get owners of the study"""
        owners = obj.get_users_by_role('owner')
        return [
            "{} ({})".format(user.get_full_name() or user.username, user.email)
            for user in owners
        ]