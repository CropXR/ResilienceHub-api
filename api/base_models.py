from django.db import models
from .permissions import set_user_role, clear_user_role, get_users_by_role 

class AccessionCodeModel(models.Model):
    """
    Abstract base model that provides automatic accession code generation.
    Subclasses must define a PREFIX class attribute.
    """
    accession_code = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        ordering = ['id']
        # Define only custom permissions here, not the built-in ones
        # Each subclass will get these permissions with its model name substituted
        permissions = [
            ('manage_permissions', 'Can manage permissions')
        ]
        
    def save(self, *args, **kwargs):
        # First save to get an ID if this is a new object
        is_new = not self.pk
        
        # If this is a new object without an accession code, we'll need to do a two-step save
        if is_new and not self.accession_code:
            # First save without the accession code to get an ID
            super().save(*args, **kwargs)
            
            # Now generate and save the accession code
            self.accession_code = f"{self.PREFIX}{self.pk}"
            # Save again with the unique accession code
            kwargs.pop('force_insert', None)  # Can't force_insert twice
            super().save(update_fields=['accession_code'])
        else:
            # For existing objects or those with a predefined accession code, just save normally
            super().save(*args, **kwargs)
            
    def __str__(self):
        return f'{self.accession_code}: {self.title}'

    def set_user_role(self, user, role):
        """Wrapper for utility function to set user role"""
        set_user_role(self, user, role)
    
    def clear_user_role(self, user):
        """Wrapper for utility function to clear user role"""
        clear_user_role(self, user)
    
    def get_users_by_role(self, role):
        """Wrapper for utility function to get users by role"""
        return get_users_by_role(self, role)