# isa_api/permissions.py
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from guardian.shortcuts import assign_perm, remove_perm, get_perms
from guardian.core import ObjectPermissionChecker
from guardian.models import GroupObjectPermission, UserObjectPermission
from rest_framework import permissions

# Use Django's built-in permission names
PERMISSION_VIEW = 'view'
PERMISSION_CHANGE = 'change' 
PERMISSION_DELETE = 'delete'
PERMISSION_MANAGE_PERMS = 'manage_permissions'  # This is our custom one

# Define role to permission mappings
ROLE_PERMISSIONS = {
    'guest': [],  # No permissions
    'internal': [PERMISSION_VIEW],  # Can view internal resources
    'authorized': [PERMISSION_VIEW],  # Read access
    'contributor': [PERMISSION_VIEW, PERMISSION_CHANGE],  # Read/write access
    'owner': [PERMISSION_VIEW, PERMISSION_CHANGE, PERMISSION_DELETE, PERMISSION_MANAGE_PERMS],  # Full access
}

#################################################################
# Django REST Framework API Permissions
#################################################################

class GuardianPermission(permissions.BasePermission):
    """
    Permission class that uses django-guardian for object-level permissions
    """
    def has_permission(self, request, view):
        # Always allow listing - queryset filtering will handle permissions
        if request.method == 'GET' and view.action == 'list':
            return True
        return True  # Defer to has_object_permission
        
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Use guardian's permission system
        if request.method in permissions.SAFE_METHODS:
            return user.has_perm(f'{obj._meta.app_label}.view_{obj._meta.model_name}', obj)
        else:
            return user.has_perm(f'{obj._meta.app_label}.change_{obj._meta.model_name}', obj)

class IsAuthorizedOrAbove(permissions.BasePermission):
    """
    Allows access to users with 'authorized' role or above for an object.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        return user.has_perm(f'{obj._meta.app_label}.view_{obj._meta.model_name}', obj)

class IsContributorOrAbove(permissions.BasePermission):
    """
    Allows access to users with 'contributor' role or above for an object.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        return user.has_perm(f'{obj._meta.app_label}.change_{obj._meta.model_name}', obj)

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Allows access only to 'owner' or 'admin' for an object.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user.is_authenticated:
            return False
            
        if user.is_superuser:
            return True
            
        # Check if user has manage_permissions permission
        return user.has_perm(f'{obj._meta.app_label}.manage_permissions_{obj._meta.model_name}', obj)

class ObjectVisibilityFilterMixin:
    """
    A mixin for viewsets to filter queryset based on object visibility.
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Create a permission checker for this user
        checker = ObjectPermissionChecker(user)
        
        # Pre-fetch permissions for all objects to avoid multiple DB queries
        model_name = queryset.model._meta.model_name
        app_label = queryset.model._meta.app_label
        view_perm = f'{app_label}.view_{model_name}'
        
        # Add objects user can see based on permissions
        visible_objects = []
        for obj in queryset:
            # Skip confidential objects in listings
            if hasattr(obj, 'security_level') and obj.security_level == 'confidential':
                continue
                
            # Check if user has view permission
            if checker.has_perm(view_perm, obj):
                visible_objects.append(obj.pk)
                
        return queryset.filter(pk__in=visible_objects)

#################################################################
# Model Mixins for Guardian
#################################################################

class GuardianMixin:
    """
    Mixin to integrate django-guardian with our RBAC model.
    """
    
    def get_permissions_for_role(self, role):
        """Get the permissions associated with a role"""
        return ROLE_PERMISSIONS.get(role, [])
    
    def assign_role(self, user, role):
        """
        Assign a role to a user for this object by granting appropriate permissions.
        """
        # Validate role
        if role not in ROLE_PERMISSIONS:
            raise ValueError(f"Invalid role: {role}")
        
        # Remove existing permissions first
        self.remove_user_permissions(user)
        
        # Get model-specific details
        app_label = self._meta.app_label
        model_name = self._meta.model_name
        
        # Assign new permissions based on role
        permissions = self.get_permissions_for_role(role)
        for perm in permissions:
            # Construct full permission name
            full_perm = f'{app_label}.{perm}_{model_name}'
            assign_perm(full_perm, user, self)
        
        # Store role information
        self.set_user_role(user, role)
    
    def remove_user_permissions(self, user):
        """
        Remove all permissions for a user on this object.
        """
        # Get current role
        current_role = self.get_user_role(user)
        
        # Check if user is the last owner
        if current_role == 'owner':
            # Count owners
            owner_count = self.get_users_by_role('owner').count()
            
            if owner_count <= 1:
                raise ValidationError(
                    "Cannot remove the last owner. Assign another owner first."
                )
        
        # Get model-specific details
        app_label = self._meta.app_label
        model_name = self._meta.model_name
        
        # Remove all existing permissions
        for perm in ROLE_PERMISSIONS['owner']:  # Use owner's full permission set
            full_perm = f'{app_label}.{perm}_{model_name}'
            remove_perm(full_perm, user, self)
        
        # Clear role information
        self.clear_user_role(user)
    
    def get_user_role(self, user):
        """
        Determine user's role based on permissions on this object.
        """
        # Handle special cases first
        if not user or not user.is_authenticated:
            return 'guest'
        
        if user.is_superuser:
            return 'admin'
        
        # Get model-specific details
        app_label = self._meta.app_label
        model_name = self._meta.model_name
        
        # Get user's permissions on this object
        user_perms = set(get_perms(user, self))
        
        # Check roles from highest to lowest
        role_hierarchy = ['owner', 'contributor', 'authorized']
        for role in role_hierarchy:
            required_perms = {
                f'{perm}_{model_name}' for perm in self.get_permissions_for_role(role)
            }
            
            if required_perms.issubset(user_perms):
                return role
        
        # Check staff status
        if user.is_staff:
            return 'internal'
        
        return 'guest'
    
    def can_read(self, user):
        """Check if user can read this object based on guardian permissions"""
        app_label = self._meta.app_label
        model_name = self._meta.model_name
        view_perm = f'{app_label}.view_{model_name}'
        
        # Check explicit permissions
        if user.has_perm(view_perm, self):
            return True
            
        # Apply security level logic if no explicit permission
        if hasattr(self, 'security_level'):
            return self._check_security_level_read(user)
            
        return False
    
    def can_write(self, user):
        """Check if user can write to this object based on guardian permissions"""
        app_label = self._meta.app_label
        model_name = self._meta.model_name
        change_perm = f'{app_label}.change_{model_name}'
        
        return user.has_perm(change_perm, self)
    
    def can_manage_permissions(self, user):
        """Check if user can manage permissions for this object"""
        app_label = self._meta.app_label
        model_name = self._meta.model_name
        manage_perm = f'{app_label}.manage_permissions_{model_name}'
        
        return user.has_perm(manage_perm, self)
    
    def _check_security_level_read(self, user):
        """
        Check read access based on security level and user type,
        following the RBAC matrix.
        """
        if not user or user.is_anonymous:
            # Anonymous users are guests
            return self.security_level == 'public'
            
        if user.is_superuser:
            return True
            
        # Get user role
        user_role = self.get_user_role(user)
        
        # Apply RBAC matrix
        if self.security_level == 'public':
            return True
            
        if self.security_level == 'internal':
            return user_role in ['internal', 'authorized', 'contributor', 'owner', 'admin']
            
        if self.security_level == 'restricted':
            return user_role in ['authorized', 'contributor', 'owner', 'admin']
            
        if self.security_level == 'confidential':
            return user_role in ['authorized', 'contributor', 'owner', 'admin']
            
        return False
    
    def is_visible(self, user):
        """Check if object should be visible in listings"""
        if hasattr(self, 'security_level') and self.security_level == 'confidential':
            # Confidential resources are not visible in listings
            return False
        return self.can_read(user)
    
    # Abstract methods to be implemented by concrete models
    def set_user_role(self, user, role):
        raise NotImplementedError("Subclasses must implement set_user_role()")
    
    def clear_user_role(self, user):
        raise NotImplementedError("Subclasses must implement clear_user_role()")
    
    def get_users_by_role(self, role):
        raise NotImplementedError("Subclasses must implement get_users_by_role()")