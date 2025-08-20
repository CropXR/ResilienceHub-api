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

class CustomUser(User):
    class Meta:
        proxy = True
    
    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

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
        ('admin', 'Dataset Administrator'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    # Generic relation fields
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'content_type', 'object_id')
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.user.username})"

    def _remove_permissions(self, role):
        """Helper method to remove permissions for a specific role."""
        from guardian.shortcuts import remove_perm
        
        role_permissions = {
            'guest': ['view'],
            'internal': ['view'],
            'authorized': ['view'],
            'contributor': ['view', 'change'],
            'owner': ['view', 'change', 'delete'],
            'admin': ['view', 'change', 'delete'],
        }
        
        if role in role_permissions and self.content_object:
            model_name = self.content_type.model
            app_label = self.content_type.app_label
            
            for action in role_permissions[role]:
                perm_code = f'{app_label}.{action}_{model_name}'
                try:
                    remove_perm(perm_code, self.user, self.content_object)
                    print(f"Removed permission {perm_code} from {self.user.username}")
                except Exception as e:
                    print(f"Error removing permission {perm_code} from {self.user.username}: {e}")

    def _assign_permissions(self, role):
        """Helper method to assign permissions for a specific role."""
        from guardian.shortcuts import assign_perm
        
        role_permissions = {
            'guest': ['view'],
            'internal': ['view'],
            'authorized': ['view'],
            'contributor': ['view', 'change'],
            'owner': ['view', 'change', 'delete'],
            'admin': ['view', 'change', 'delete'],
        }
        
        if role in role_permissions and self.content_object:
            model_name = self.content_type.model
            app_label = self.content_type.app_label
            
            for action in role_permissions[role]:
                perm_code = f'{app_label}.{action}_{model_name}'
                try:
                    assign_perm(perm_code, self.user, self.content_object)
                    print(f"Assigned permission {perm_code} to {self.user.username}")
                except Exception as e:
                    print(f"Error assigning permission {perm_code} to {self.user.username}: {e}")

    def delete(self, *args, **kwargs):
        """Remove Guardian permissions when UserRole is deleted."""
        self._remove_permissions(self.role)
        super().delete(*args, **kwargs)
    
    def save(self, *args, **kwargs):
        """Assign Guardian permissions when UserRole is saved."""
        old_role = None
        
        # Check if this is an update vs new creation
        if self.pk:
            try:
                old_instance = UserRole.objects.get(pk=self.pk)
                old_role = old_instance.role
            except UserRole.DoesNotExist:
                pass
        
        # Save the model first
        super().save(*args, **kwargs)
        
        # If role changed, remove old permissions first
        if old_role and old_role != self.role:
            self._remove_permissions(old_role)
        
        # Assign new permissions
        self._assign_permissions(self.role)
        
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
    
    principal_investigator = models.ForeignKey(
        CustomUser,
        related_name='principal_investigations',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Principal investigator for this investigation"
    )
        
    class Meta:
        permissions = [
            ('manage_permissions_investigation', 'Can manage permissions for investigation'),
        ]
        ordering = ['id']

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
    
    dataset_administrator = models.ForeignKey(
        CustomUser,
        related_name='dataset_administrations',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Dataset administrator for this study"
    )

    def principal_investigator(self):
        """
        Return the principal investigator for this study.
        """
        return self.investigation.principal_investigator if self.investigation else None
    
    security_level = models.CharField(
        max_length=20,
        choices=SecurityLevel.choices,
        default=SecurityLevel.CONFIDENTIAL
    )
    
    def __str__(self):
        return f"{self.accession_code} - {self.slug}"
    
    def work_package(self):
        """
        Return the work package of the parent investigation.
        """
        return self.investigation.work_package if self.investigation else None
    
    work_package.admin_order_field = 'investigation__work_package'

    def folder_name(self):
        folder_name = f"s_{self.investigation.work_package}-{self.investigation.accession_code}-{self.accession_code}"
        if self.slug:
            folder_name += f"_{self.slug}"
        return folder_name
        
    class Meta:
        permissions = [
            ('manage_permissions_study', 'Can manage permissions for study'),
        ]        
        ordering = ['id']
            
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
