from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django import forms
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_users_with_perms, get_objects_for_user  # Added missing import

from .models import (
    Investigation, Study, Assay, 
    UserRole, Institution, Sample, 
    InvestigationInstitution,
    CustomUser
)
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.auth.admin import UserAdmin



class CustomGuardedModelAdmin(GuardedModelAdmin):
    def get_queryset(self, request):
        """
        Filters the queryset to show only objects the user has permission to view
        """
        qs = super().get_queryset(request)
        
        # Superusers see everything
        if request.user.is_superuser:
            return qs
        
        # Get the model name for permission checking
        model_name = qs.model._meta.model_name
        app_label = qs.model._meta.app_label
        view_perm = f'{app_label}.view_{model_name}'
        
        # Filter queryset to objects user can view
        return qs.filter(pk__in=[
            obj.pk for obj in get_objects_for_user(request.user, view_perm, qs)
        ])
    
    def has_view_permission(self, request, obj=None):
        """
        Check view permission for a specific object
        """
        # Superusers always have permission
        if request.user.is_superuser:
            return True
        
        # If no specific object, allow listing
        if obj is None:
            return True
        
        # Check object-level view permission
        model_name = obj._meta.model_name
        app_label = obj._meta.app_label
        view_perm = f'{app_label}.view_{model_name}'
        
        return request.user.has_perm(view_perm, obj)
    
    def has_change_permission(self, request, obj=None):
        """
        Check change permission for a specific object
        """
        # Superusers always have permission
        if request.user.is_superuser:
            return True
        
        # If no specific object, allow listing
        if obj is None:
            return True
        
        # Check object-level change permission
        model_name = obj._meta.model_name
        app_label = obj._meta.app_label
        change_perm = f'{app_label}.change_{model_name}'
        
        return request.user.has_perm(change_perm, obj)
    
    def has_delete_permission(self, request, obj=None):
        """
        Check delete permission for a specific object
        """
        # Superusers always have permission
        if request.user.is_superuser:
            return True
        
        # If no specific object, disallow delete
        if obj is None:
            return False
        
        # Check object-level delete permission
        model_name = obj._meta.model_name
        app_label = obj._meta.app_label
        delete_perm = f'{app_label}.delete_{model_name}'
        
        return request.user.has_perm(delete_perm, obj)

class UserRoleInline(GenericTabularInline):
    model = UserRole
    extra = 1
    verbose_name = "User Permission"
    verbose_name_plural = "User Permissions"
    autocomplete_fields = ['user']

class StudyInline(admin.TabularInline):
    model = Study
    extra = 0
    readonly_fields = ['investigation', 'accession_code_link']
    fields = ['investigation', 'accession_code_link', 'title']

    def accession_code_link(self, obj):
        """Create a clickable link to the Study detail page."""
        url = reverse('admin:api_study_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.accession_code)

    accession_code_link.short_description = 'Accession Code'

    def has_change_permission(self, request, obj=None):
        return True

class InstitutionInline(admin.TabularInline):
    model = InvestigationInstitution
    extra = 0

class InvestigationAdminForm(forms.ModelForm):
    class Meta:
        model = Investigation
        exclude = []

    def clean(self):
        cleaned_data = super().clean()
        # Skip ownership validation during initial save
        return cleaned_data

@admin.register(Investigation)
class InvestigationAdmin(CustomGuardedModelAdmin):
    form = InvestigationAdminForm

    list_display = ('id', 'accession_code', 'work_package', 'title', 'security_level', 'user_count')
    list_display_links = ('accession_code', 'title')
    search_fields = ('accession_code', 'title', 'description')
    list_filter = ('security_level', 'submission_date', 'public_release_date')
    ordering = ('id',)
    readonly_fields = ('id', 'accession_code', 'created_at', 'updated_at')
    inlines = [UserRoleInline, StudyInline, InstitutionInline]
    
    fields = (
        'accession_code',
        'work_package',
        'title',
        'description',
        'security_level',
        'submission_date',
        'public_release_date',
        'created_at',
        'updated_at',
        'principal_investigator_name',
        'principal_investigator_email',
        'principal_investigator',
        'notes'
    )   
    
    def user_count(self, obj):
        """Count users with permissions on this object."""
        users = get_users_with_perms(obj)
        return len(users)
    
    user_count.short_description = "Users"
    
    def save_model(self, request, obj, form, change):
        """When creating a new object, assign owner permissions to current user."""
        is_new = not change  # True if this is a new object being created
        super().save_model(request, obj, form, change)
        
        if is_new:
            # Assign owner role to the current user
            obj.set_user_role(request.user, 'owner')

class AssayInline(admin.TabularInline):
    model = Assay
    extra = 0
    readonly_fields = ['accession_code_link']  # Fixed trailing comma
    fields = ['accession_code_link', 'title']

    def accession_code_link(self, obj):
        """Create a clickable link to the Assay detail page."""
        url = reverse('admin:api_assay_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.accession_code)

    accession_code_link.short_description = 'Accession Code'

@admin.register(Study)
class StudyAdmin(CustomGuardedModelAdmin):
    list_display = ('id', 'accession_code', 'investigation_link', 'work_package', 'slug', 
                    'title', 'submission_date', 'security_level', 'user_count')
    list_display_links = ('accession_code', 'title')
    search_fields = ('accession_code', 'title', 'description', 'investigation__accession_code')
    list_filter = ('investigation', 'submission_date', 'security_level')
    ordering = ('id',)
    readonly_fields = ('id', 'accession_code', 'work_package', 'accession_code', 'created_at', 'updated_at', 'folder_name', 'principal_investigator')
    
    fields = (
        'accession_code',       
        'work_package',
        'investigation', 
        'title', 
        'security_level', 
        'slug', 
        'description',
        'principal_investigator_name',
        'principal_investigator_email',
        'principal_investigator',
        'dataset_administrator',
        'notes', 
        'start_date', 
        'end_date', 
        'submission_date', 
        'folder_name'          
    )
    
    
    def investigation_link(self, obj):
        url = reverse('admin:api_investigation_change', args=[obj.investigation.id])
        return format_html('<a href="{}">{}</a>', url, obj.investigation.accession_code)
    
    investigation_link.short_description = "Investigation"
    
    def user_count(self, obj):
        """Count users with permissions on this object."""
        users = get_users_with_perms(obj)
        return len(users)
    
    user_count.short_description = "Users"
    
    #inlines = [UserRoleInline, AssayInline]
    inlines = [UserRoleInline]
    
    
    def save_model(self, request, obj, form, change):
        """When creating a new object, assign owner permissions to current user."""
        is_new = not change  # True if this is a new object being created
        super().save_model(request, obj, form, change)
        
        if is_new:
            # Assign owner role to the current user
            obj.set_user_role(request.user, 'owner')

#@admin.register(Assay)  # Commented out admin registration
class AssayAdmin(CustomGuardedModelAdmin):
    list_display = ('id', 'accession_code', 'study_link', 'investigation_link', 'title', 
                    'measurement_type')
    list_display_links = ('accession_code',)
    search_fields = ('accession_code', 'description', 'study__accession_code', 'study__title')
    list_filter = ('study__investigation', 'study', 'measurement_type')  # Fixed trailing comma
    ordering = ('id',)
    readonly_fields = ('id', 'accession_code', 'created_at', 'updated_at', 'study')
    fields = ('study', 
              'accession_code', 
              'title', 
              'description',             
              'measurement_type', 
              'created_at', 
              'updated_at'
             )
    inlines = [UserRoleInline]

    def study_link(self, obj):
        """Create a clickable link to the Study detail page."""
        url = reverse('admin:api_study_change', args=[obj.study.id])
        return format_html('<a href="{}">{}</a>', url, obj.study.accession_code)
    
    study_link.short_description = "Study"

    def investigation_link(self, obj):
        """Create a clickable link to the Investigation detail page."""
        if obj.study and obj.study.investigation:
            url = reverse('admin:api_investigation_change', args=[obj.study.investigation.id])
            return format_html('<a href="{}">{}</a>', url, obj.study.investigation.accession_code)
        return "-"

    investigation_link.short_description = "Investigation"

# @admin.register(UserRole)  # Commented out admin registration
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'role', 'content_type', 'object_id', 'created_at')
    list_filter = ('role', 'content_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'object_id')
    autocomplete_fields = ['user']

@admin.register(Institution)  # Commented out admin registration
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'address_street', 'address_house_number', 'address_addition', 'address_postcode', 'address_city', 'address_country']
    search_fields = ['name']

@admin.register(Sample)  # Commented out admin registration
class SampleAdmin(CustomGuardedModelAdmin):
    list_display = ['accession_code', 'id', 'name', 'security_level']
    search_fields = ['accession_code', 'name']
    readonly_fields = ['accession_code']
    fields = ['accession_code', 'name', 'sample_type', 'security_level']
    inlines = [UserRoleInline]

#@admin.register(InvestigationInstitution)  # Commented out admin registration
class InvestigationInstitutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'institution', 'contribution_amount', 'join_date']
    search_fields = ['project__title', 'institution__name']
    autocomplete_fields = ['project', 'institution']    
    
admin.site.site_header = "ResilienceHub API"
admin.site.site_title = "ResilienceHub Admin"
admin.site.index_title = "Welcome to ResilienceHub Admin"

# Register with your proxy model
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    pass  # Inherits all the original UserAdmin functionality