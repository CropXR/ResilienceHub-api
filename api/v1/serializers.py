# isa_api/v1/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import (
    Investigation, 
    Study, 
    Assay, 
    SecurityLevel, 
    UserRole, 
    Institution,
    Sample
)
from typing import List, Dict, Any
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from ..permissions import GuardianPermission, IsOwnerOrAdmin


@extend_schema_serializer(component_name="UserV1")
class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, obj):
        full_name = obj.get_full_name() or obj.username
        return f"{full_name} ({obj.email})"

    class Meta:
        model = User
        fields = ['display_name']

class InvestigationSerializer(serializers.ModelSerializer):
    studies = serializers.SerializerMethodField()
    #owners = serializers.SerializerMethodField()
    #contributors = serializers.SerializerMethodField()
    #readers = serializers.SerializerMethodField()
    
    # Add this if it's a many-to-many or foreign key relationship
    #participating_institutions = serializers.PrimaryKeyRelatedField(
    #    queryset=Institution.objects.all(),
    #    many=True,
    #    required=False
    #)

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
            'start_date',
            'end_date',
            'submission_date',
            'public_release_date', 
            'created_at', 
            'updated_at', 
            'studies',
            #'owners',
            #'contributors',
            #'readers',
            #'participating_institutions'
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
        owners = obj.get_users_by_role(UserRole.OWNER)
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in owners
        ]
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_contributors(self, obj) -> List[str]:
        """Get contributors of the investigation"""
        contributors = obj.get_users_by_role(UserRole.CONTRIBUTOR)
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in contributors
        ]
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_readers(self, obj) -> List[str]:
        """Get readers of the investigation"""
        readers = obj.get_users_by_role(UserRole.VIEWER)
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in readers
        ]

class StudySerializer(serializers.ModelSerializer):
    investigation_accession = serializers.CharField(source='investigation.accession_code', read_only=True)
    #assays = serializers.SerializerMethodField()
    #owners = serializers.SerializerMethodField()
    #contributors = serializers.SerializerMethodField()
    #readers = serializers.SerializerMethodField()
    
    class Meta:
        model = Study
        fields = [
            'accession_code',
            'investigation_accession', 
            'title', 
            'description', 
            'submission_date', 
            'study_design', 
            'start_date',
            'end_date',
            #'created_at', 
            #'updated_at',
            'assays',
            'security_level',
            #'owners',
            #'contributors',
            #'readers'
        ]
        read_only_fields = ['accession_code', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If the instance is new, remove 'assays' field
        if not self.instance:
            self.fields.pop('assays')

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
        owners = obj.get_users_by_role(UserRole.OWNER)
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in owners
        ]
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_contributors(self, obj) -> List[str]:
        """Get contributors of the study"""
        contributors = obj.get_users_by_role(UserRole.CONTRIBUTOR)
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in contributors
        ]
    
    @extend_schema_field({'type': 'array', 'items': {'type': 'string'}})
    def get_readers(self, obj) -> List[str]:
        """Get readers of the study"""
        readers = obj.get_users_by_role(UserRole.VIEWER)
        return [
            f"{user.get_full_name() or user.username} ({user.email})"
            for user in readers
        ]

class AssaySerializer(serializers.ModelSerializer):
    study_accession = serializers.CharField(source='study.accession_code', read_only=True)
    investigation_accession = serializers.CharField(source='study.investigation.accession_code', read_only=True)
    
    class Meta:
        model = Assay
        fields = [
            'accession_code', 
            'study_accession',
            'title',
            'investigation_accession',
            'measurement_type', 
            'description', 
            'created_at', 
            'updated_at'
        ]
        read_only_fields = ['study_accession', 'accession_code', 'created_at', 'updated_at']
        
class SampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sample
        fields = [
            'accession_code', 
            'sample_type'
        ]
        read_only_fields = ['accession_code']
        