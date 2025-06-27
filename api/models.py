# api/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from guardian.models import UserObjectPermission
from guardian.shortcuts import get_users_with_perms, remove_perm

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from .choices import SecurityLevel, MeasurementType, TechnologyPlatform, WorkPackageChoices
from .base_models import AccessionCodeModel
from .permissions import GuardianMixin

from django_countries.fields import CountryField


class UserRole(models.Model):
    """
    Stores user roles for objects since django-guardian doesn't have a built-in role concept.
    """
    ROLE_CHOICES = [
        ('guest', 'Guest'),
        ('internal', 'Internal'),
        ('authorized', 'Authorized'),
        ('contributor', 'Contributor'),
        ('owner', 'Owner'),
        ('admin', 'Admin'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    # Generic relation fields
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')  # Add this line
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'content_type', 'object_id')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.user.username})"

class Institution(models.Model):
    name = models.CharField(max_length=500)
    website = models.URLField(blank=True, null=True, max_length=500)
    address_street = models.CharField(blank=True, null=True, max_length=500)
    address_house_number = models.CharField(blank=True, null=True, max_length=10)
    address_addition = models.CharField(blank=True, null=True, max_length=100)
    address_postcode = models.CharField(blank=True, null=True, max_length=10)
    address_city = models.CharField(blank=True, null=True, max_length=100)
    address_country = CountryField()
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name


class Investigation(AccessionCodeModel, GuardianMixin):
    PREFIX = 'CXRP'
    title = models.CharField(max_length=1000)
    description = models.TextField(null=True,blank=True)

    work_package = models.CharField(
        max_length=10,
        choices=WorkPackageChoices.choices,
        blank=True,
        null=True,
        help_text="Select the primary work package for this investigation",
    )
    notes = models.TextField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    submission_date = models.DateField(blank=True, null=True)
    public_release_date = models.DateField(blank=True, null=True)
    principal_investigator_name = models.CharField(max_length=255, null=True, blank=True)
    principal_investigator_email = models.EmailField(max_length=255, null=True, blank=True)
    
    security_level = models.CharField(
        max_length=20,
        choices=SecurityLevel.choices,
        default=SecurityLevel.CONFIDENTIAL
    )

    participating_institutions = models.ManyToManyField(
        Institution, 
        related_name='research_projects',
        through='InvestigationInstitution',
    )
        
    class Meta:
        permissions = [
            ('manage_permissions_investigation', 'Can manage permissions for investigation'),
        ]
        ordering = ['id']

    def has_owners(self):
        """
        Check if this object has at least one owner.
        Consistent implementation across different model types.
        """
        return self.get_users_by_role('owner').exists()

    def set_default_owner(self, user):
        """
        Set the default owner for the object when created.
        Use this in create methods or during object initialization.
        """
        # Assign owner role
        self.set_user_role(user, 'owner')

    def create(self, validated_data):
        user = self.context['request'].user
        investigation = Investigation.objects.create(**validated_data)
        investigation.set_user_role(user, UserRole.OWNER)
        return investigation


class InvestigationInstitution(models.Model):
    project = models.ForeignKey(Investigation, on_delete=models.CASCADE)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    contribution_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    join_date = models.DateField()
    
    class Meta:
        unique_together = ('project', 'institution')
        verbose_name = "Institution"
        verbose_name_plural = "Institutions"


class Study(AccessionCodeModel, GuardianMixin):
    PREFIX = 'CXRS'
    investigation = models.ForeignKey(Investigation, related_name='studies', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    slug = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        validators=[
            RegexValidator(
                regex='^[a-zA-Z0-9_-]+$',
                message='Slug label must contain only alphanumeric characters, underscores, and hyphens (no spaces or special characters)',
                code='invalid_label'
            )
        ]
    )
    description = models.TextField(null=True,blank=True)
    notes = models.TextField(blank=True, null=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True,blank=True)
    public_release_date = models.DateField(null=True,blank=True)
    submission_date = models.DateField(null=True,blank=True)
    study_design = models.TextField(null=True,blank=True)
    
    principal_investigator_name = models.CharField(max_length=255, null=True, blank=True)
    principal_investigator_email = models.EmailField(max_length=255, null=True, blank=True)
    
    security_level = models.CharField(
        max_length=20,
        choices=SecurityLevel.choices,
        default=SecurityLevel.CONFIDENTIAL
    )
    
    def __str__(self):
        return f"{self.accession_code} - {self.slug}"
    
    def folder_name(self):
        folder_name = f"i_{self.investigation.work_package}_{self.investigation.accession_code}/s_{self.investigation.accession_code}-{self.accession_code}"
        if self.slug:
            folder_name += f"__{self.slug}"
        return folder_name
        
    class Meta:
        permissions = [
            ('manage_permissions_study', 'Can manage permissions for study'),
        ]        
        ordering = ['id']

    def has_owners(self):
        """Check if this study has at least one owner."""
        return self.get_users_by_role('owner').exists()
            
    def _check_security_level_read(self, user):
        """
        Enhanced security level check that also considers investigation permissions.
        """
        # First check basic security level permissions
        basic_access = super()._check_security_level_read(user)
        if basic_access:
            return True
            
        # If no direct access, check if user has investigation-level access
        if self.investigation:
            # Get user's role at the investigation level
            inv_role = self.investigation.get_user_role(user)
            
            # Apply RBAC matrix logic based on investigation role
            if self.security_level == 'public':
                return True
                
            if self.security_level == 'internal':
                return inv_role in ['internal', 'authorized', 'contributor', 'owner', 'admin']
                
            if self.security_level == 'restricted':
                return inv_role in ['authorized', 'contributor', 'owner', 'admin']
                
            if self.security_level == 'confidential':
                return inv_role in ['owner', 'admin']
                
        return False

    def create(self, validated_data):
        user = self.context['request'].user
        study = Study.objects.create(**validated_data)
        study.set_user_role(user, 'owner')
        return study

class Assay(AccessionCodeModel, GuardianMixin):
    PREFIX = 'CXRA'
    
    study = models.ForeignKey(Study, related_name='assays', on_delete=models.CASCADE)
    measurement_type = models.CharField(max_length=50, choices=MeasurementType.choices)
    title = models.CharField(max_length=1000)
    technology_platform = models.CharField(max_length=50, choices=TechnologyPlatform.choices)
    description = models.TextField()
    
    @property
    def security_level(self):
        """Get security level from parent Study"""
        return self.study.security_level if self.study else SecurityLevel.CONFIDENTIAL

    def investigation(self):
        """Access investigation from related study"""
        return self.study.investigation if self.study else None

    investigation.admin_order_field = 'study__investigation'
    investigation.short_description = 'Investigation'
    
    def set_user_role(self, user, role):
        """Wrapper for utility function to set user role"""
        set_user_role(self, user, role)
    
    def clear_user_role(self, user):
        """Wrapper for utility function to clear user role"""
        clear_user_role(self, user)
    
    def get_users_by_role(self, role):
        """Wrapper for utility function to get users by role"""
        return get_users_by_role(self, role)
    
    def _check_security_level_read(self, user):
        """
        Enhanced security level check that delegates to the study.
        """
        # Delegate to study's security logic
        if self.study:
            return self.study._check_security_level_read(user)
        return False


class Sample(AccessionCodeModel, GuardianMixin):
    PREFIX = 'CXRX'
    security_level = models.CharField(
        max_length=20,
        choices=SecurityLevel.choices,
        default=SecurityLevel.CONFIDENTIAL
    )
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    sample_type = models.CharField(max_length=50)
    
