from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.utils import IntegrityError
from isa_api.models import (
    Investigation, 
    Study, 
    Assay, 
    SecurityLevel
)
from isa_api.permissions import (
    PERMISSION_VIEW,
    PERMISSION_CHANGE,
    PERMISSION_DELETE,
    PERMISSION_MANAGE_PERMS,
    ROLE_PERMISSIONS,
    GuardianMixin
)
from django.utils import timezone

class PermissionMatrixTestBase(TestCase):
    """Base class for permission matrix tests"""
    
    def _create_permission_safely(self, codename, name, content_type):
        """
        Create a permission safely, handling any integrity errors.
        This method ensures we don't get UNIQUE constraint errors.
        """
        # First try to get the permission
        try:
            perm = Permission.objects.get(
                codename=codename,
                content_type=content_type
            )
            return perm
        except Permission.DoesNotExist:
            # If it doesn't exist, try to create it
            try:
                perm = Permission.objects.create(
                    codename=codename,
                    name=name,
                    content_type=content_type
                )
                return perm
            except IntegrityError:
                # If we get an integrity error, someone else might have created it
                # Try one more time to get it
                return Permission.objects.get(
                    codename=codename,
                    content_type=content_type
                )
    
    def _create_guardian_permissions(self, model_class, model_name):
        """
        Create the necessary custom permissions for guardian in the test database.
        Note: Django's default permissions (view, change, delete) are already created.
        """
        content_type = ContentType.objects.get_for_model(model_class)
        # Only create our custom permission
        self._create_permission_safely(
            codename=f'{PERMISSION_MANAGE_PERMS}_{model_name}',
            name=f'Can {PERMISSION_MANAGE_PERMS} {model_name}',
            content_type=content_type
        )
    
    def _setup_users(self):
        """Create test users with different roles"""
        self.guest_user = User.objects.create_user(username='guest', password='password')
        self.internal_user = User.objects.create_user(username='internal', password='password', is_staff=True)
        self.authorized_user = User.objects.create_user(username='authorized', password='password')
        self.contributor_user = User.objects.create_user(username='contributor', password='password')
        self.owner_user = User.objects.create_user(username='owner', password='password')
        # Using Django's superuser instead of a specific 'admin' role
        self.admin_user = User.objects.create_user(username='superuser', password='password', is_superuser=True)
    
    def _test_permission_matrix(self, resource, security_level, expected_access):
        """
        Test the permission matrix for a given resource and security level.
        
        Args:
            resource: The resource to test permissions on (Investigation or Study)
            security_level: The security level to set for the resource
            expected_access: Dict mapping user types to expected (can_read, can_write) tuples
        """
        # Set security level
        resource.security_level = security_level
        resource.save()
        
        # Test each user type
        for user_type, user in [
            ('guest', self.guest_user),
            ('internal', self.internal_user),
            ('authorized', self.authorized_user),
            ('contributor', self.contributor_user),
            ('owner', self.owner_user),
            ('superuser', self.admin_user),  # Django's built-in superuser, not a specific role
        ]:
            if user_type not in expected_access:
                continue
                
            expected_read, expected_write = expected_access[user_type]
            
            # Check read access
            can_read = resource.can_read(user)
            self.assertEqual(can_read, expected_read, 
                f"{user_type} should{'not ' if not expected_read else ' '}be able to read {security_level} resource")
            
            # Check write access
            can_write = resource.can_write(user)
            self.assertEqual(can_write, expected_write, 
                f"{user_type} should{'not ' if not expected_write else ' '}be able to write to {security_level} resource")

class InvestigationPermissionMatrixTest(PermissionMatrixTestBase):
    """Test the permission matrix for investigations"""
    
    def setUp(self):
        # Create test users
        self._setup_users()
        
        # Create permissions
        self._create_guardian_permissions(Investigation, 'investigation')
        
        # Create a test investigation
        self.investigation = Investigation.objects.create(
            title='Test Investigation',
            description='Test Description',
            submission_date=timezone.now().date(),
            public_release_date=timezone.now().date() + timezone.timedelta(days=30),
            security_level=SecurityLevel.PUBLIC  # Default to public
        )
        
        # Assign roles
        self.investigation.assign_role(self.authorized_user, 'authorized')
        self.investigation.assign_role(self.contributor_user, 'contributor')
        self.investigation.assign_role(self.owner_user, 'owner')
    
    def test_public_investigation(self):
        """Test access to a public investigation"""
        expected_access = {
            'guest': (True, False),  # Can read, can't write
            'internal': (True, False),
            'authorized': (True, False),
            'contributor': (True, True),  # Can read and write
            'owner': (True, True),
            'superuser': (True, True),  # Django superuser has full access
        }
        self._test_permission_matrix(self.investigation, SecurityLevel.PUBLIC, expected_access)
    
    def test_internal_investigation(self):
        """Test access to an internal investigation"""
        expected_access = {
            'guest': (False, False),  # No access
            'internal': (True, False),  # Can read
            'authorized': (True, False),
            'contributor': (True, True),  # Can read and write
            'owner': (True, True),
            'admin': (True, True),
        }
        self._test_permission_matrix(self.investigation, SecurityLevel.INTERNAL, expected_access)
    
    def test_restricted_investigation(self):
        """Test access to a restricted investigation"""
        expected_access = {
            'guest': (False, False),  # No access
            'internal': (False, False),
            'authorized': (True, False),  # Can read if authorized
            'contributor': (True, True),  # Can read and write if authorized
            'owner': (True, True),
            'admin': (True, True),
        }
        self._test_permission_matrix(self.investigation, SecurityLevel.RESTRICTED, expected_access)
    
    def test_confidential_investigation(self):
        """Test access to a confidential investigation"""
        expected_access = {
            'guest': (False, False),  # No access
            'internal': (False, False),
            'authorized': (True, False),  # Can read if explicitly authorized
            'contributor': (True, True),  # Can read and write if explicitly authorized
            'owner': (True, True),
            'admin': (True, True),
        }
        self._test_permission_matrix(self.investigation, SecurityLevel.CONFIDENTIAL, expected_access)

class StudyPermissionMatrixTest(PermissionMatrixTestBase):
    """Test the permission matrix for studies"""
    
    def setUp(self):
        # Create test users
        self._setup_users()
        
        # Create permissions
        self._create_guardian_permissions(Investigation, 'investigation')
        self._create_guardian_permissions(Study, 'study')
        
        # Create a test investigation
        self.investigation = Investigation.objects.create(
            title='Test Investigation',
            description='Test Description',
            submission_date=timezone.now().date(),
            public_release_date=timezone.now().date() + timezone.timedelta(days=30),
            security_level=SecurityLevel.PUBLIC
        )
        
        # Create a test study
        self.study = Study.objects.create(
            investigation=self.investigation,
            title='Test Study',
            description='Test Study Description',
            study_label='STUDY1',
            submission_date=timezone.now().date(),
            study_design='Test Design',
            security_level=SecurityLevel.PUBLIC  # Default to public
        )
        
        # Assign roles for the study
        self.study.assign_role(self.authorized_user, 'authorized')
        self.study.assign_role(self.contributor_user, 'contributor')
        self.study.assign_role(self.owner_user, 'owner')
    
    def test_public_study(self):
        """Test access to a public study"""
        expected_access = {
            'guest': (True, False),  # Can read, can't write
            'internal': (True, False),
            'authorized': (True, False),
            'contributor': (True, True),  # Can read and write
            'owner': (True, True),
            'admin': (True, True),
        }
        self._test_permission_matrix(self.study, SecurityLevel.PUBLIC, expected_access)
    
    def test_internal_study(self):
        """Test access to an internal study"""
        expected_access = {
            'guest': (False, False),  # No access
            'internal': (True, False),  # Can read
            'authorized': (True, False),
            'contributor': (True, True),  # Can read and write
            'owner': (True, True),
            'admin': (True, True),
        }
        self._test_permission_matrix(self.study, SecurityLevel.INTERNAL, expected_access)
    
    def test_restricted_study(self):
        """Test access to a restricted study"""
        expected_access = {
            'guest': (False, False),  # No access
            'internal': (False, False),
            'authorized': (True, False),  # Can read if authorized
            'contributor': (True, True),  # Can read and write if authorized
            'owner': (True, True),
            'admin': (True, True),
        }
        self._test_permission_matrix(self.study, SecurityLevel.RESTRICTED, expected_access)
    
    def test_confidential_study(self):
        """Test access to a confidential study"""
        expected_access = {
            'guest': (False, False),  # No access
            'internal': (False, False),
            'authorized': (True, False),  # Can read if explicitly authorized
            'contributor': (True, True),  # Can read and write if explicitly authorized
            'owner': (True, True),
            'admin': (True, True),
        }
        self._test_permission_matrix(self.study, SecurityLevel.CONFIDENTIAL, expected_access)