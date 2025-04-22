# api/permissions.py
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from guardian.shortcuts import assign_perm, remove_perm, get_perms
from guardian.core import ObjectPermissionChecker
from guardian.models import GroupObjectPermission, UserObjectPermission
from rest_framework import permissions
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType

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
    
def set_user_role(obj, user, role, user_role_model=None):
    """
    Assign a role and corresponding permissions to a user for a specific object.

    Args:
        obj: The model instance to assign permissions for (Investigation, Study, etc.).
        user: The user to assign the role to.
        role: The role to assign (e.g., 'owner', 'contributor').
        user_role_model: Optional UserRole model to use for role assignment.

    Raises:
        ValueError: If an invalid role is provided.

    Notes:
        This method:
        - Creates or updates the user's role
        - Removes unnecessary existing permissions
        - Assigns new permissions based on the role
    """
    # Validate role
    if role not in ROLE_PERMISSIONS:
        raise ValueError(f"Invalid role: {role}")

    # Dynamically import UserRole if not provided
    if user_role_model is None:
        from .models import UserRole
    else:
        UserRole = user_role_model

    # Get content type
    content_type = ContentType.objects.get_for_model(obj)

    # Create or update UserRole
    UserRole.objects.update_or_create(
        user=user,
        content_type=content_type,
        object_id=obj.id,
        defaults={'role': role}
    )

    # Get app and model details
    app_label = obj._meta.app_label
    model_name = obj._meta.model_name

    # Remove existing permissions not in new role
    current_perms = get_perms(user, obj)
    
    # Generate full permission names
    new_permissions = [
        f'{app_label}.{perm}_{model_name}' 
        for perm in ROLE_PERMISSIONS.get(role, [])
    ]

    # Remove unnecessary permissions
    for perm in current_perms:
        if perm not in new_permissions:
            remove_perm(perm, user, obj)

    # Assign new permissions
    for perm in new_permissions:
        assign_perm(perm, user, obj)

def clear_user_role(obj, user, user_role_model=None):
    """
    Remove a user's role and all associated permissions from an object.

    Args:
        obj: The model instance to remove permissions from.
        user: The user to remove the role from.
        user_role_model: Optional UserRole model to use for role removal.

    Raises:
        ValueError: If attempting to remove the last owner of an object.

    Notes:
        This method:
        - Checks for last owner constraint
        - Removes the UserRole entry
        - Removes all associated permissions
    """
    # Dynamically import UserRole if not provided
    if user_role_model is None:
        from .models import UserRole
    else:
        UserRole = user_role_model

    # Get content type
    content_type = ContentType.objects.get_for_model(obj)

    # Check if removing last owner (if applicable)
    try:
        # Count owners
        current_role = get_user_role(obj, user, user_role_model)
        if current_role == 'owner':
            owner_count = len(get_users_by_role(obj, 'owner', user_role_model))
            if owner_count <= 1:
                raise ValueError("Cannot remove the last owner")
    except Exception:
        # If method doesn't exist or fails, skip the check
        pass

    # Remove UserRole
    UserRole.objects.filter(
        user=user,
        content_type=content_type,
        object_id=obj.id
    ).delete()

    # Remove all permissions
    app_label = obj._meta.app_label
    model_name = obj._meta.model_name
    
    # Remove all potential permissions
    for perm_type in ['view', 'change', 'delete', 'manage_permissions']:
        full_perm = f'{app_label}.{perm_type}_{model_name}'
        try:
            remove_perm(full_perm, user, obj)
        except:
            pass

def get_users_by_role(obj, role, user_role_model=None):
    """
    Retrieve all users with a specific role for a given object.

    Args:
        obj: The model instance to query roles for.
        role: The role to filter by (e.g., 'owner', 'contributor').
        user_role_model: Optional UserRole model to use for querying.

    Returns:
        QuerySet: A distinct set of users with the specified role.

    Example:
        owners = get_users_by_role(my_study, 'owner')
    """
    # Dynamically import UserRole if not provided
    if user_role_model is None:
        from .models import UserRole
    else:
        UserRole = user_role_model

    # Get content type
    content_type = ContentType.objects.get_for_model(obj)

    # Query UserRole entries
    role_assignments = UserRole.objects.filter(
        content_type=content_type,
        object_id=obj.id,
        role=role
    )

    # Return users
    return User.objects.filter(roles__in=role_assignments).distinct()

def get_user_role(obj, user, user_role_model=None):
    """
    Determine the role of a user for a specific object.

    Args:
        obj: The model instance to check role for.
        user: The user to check the role of.
        user_role_model: Optional UserRole model to use for querying.

    Returns:
        str: The user's role (e.g., 'owner', 'contributor', 'guest').
             Defaults to 'guest' if no specific role is found.

    Example:
        user_role = get_user_role(my_investigation, current_user)
    """
    # Dynamically import UserRole if not provided
    if user_role_model is None:
        from .models import UserRole
    else:
        UserRole = user_role_model

    # Handle special cases
    if not user or not user.is_authenticated:
        return 'guest'

    if user.is_superuser:
        return 'admin'

    # Get content type
    content_type = ContentType.objects.get_for_model(obj)

    try:
        # Try to get the specific UserRole
        user_role = UserRole.objects.get(
            user=user,
            content_type=content_type,
            object_id=obj.id
        )
        return user_role.role
    except UserRole.DoesNotExist:
        # Default to guest if no role found
        return 'guest'