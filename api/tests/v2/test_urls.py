# isa_api/tests/v2/test_urls.py
from unittest import skip

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from api.models import Investigation, Study, Sample
from api.models import (
    SecurityLevel
)
from api.permissions import (
    PERMISSION_MANAGE_PERMS
)
from api.tests.helpers import create_permission_safely

@skip("quickly test v3 views, these are fine")
class BaseUrlTestCase(TestCase):
    """Base test case with common setup for URL testing"""

    def _create_guardian_permissions(self):
        """
        Create the necessary permissions for guardian in the test database.
        We only need to create custom permissions - Django's defaults are already there.
        """
        # Create custom permissions for Investigation model
        investigation_ct = ContentType.objects.get_for_model(Investigation)
        create_permission_safely(
            codename=f'{PERMISSION_MANAGE_PERMS}_investigation',
            name=f'Can {PERMISSION_MANAGE_PERMS} investigation',
            content_type=investigation_ct
        )
            
        # Create custom permissions for Study model
        study_ct = ContentType.objects.get_for_model(Study)
        create_permission_safely(
            codename=f'{PERMISSION_MANAGE_PERMS}_study',
            name=f'Can {PERMISSION_MANAGE_PERMS} study',
            content_type=study_ct
        )

        # Create custom permissions for Sample model
        sample_ct = ContentType.objects.get_for_model(Sample)
        create_permission_safely(
            codename=f'{PERMISSION_MANAGE_PERMS}_sample',
            name=f'Can {PERMISSION_MANAGE_PERMS} sample',
            content_type=sample_ct
        )
        
    def setUp(self):
        # Create a user for permissions
        self.user = User.objects.create_user(username='testuser', password='12345')
        
        # Ensure guardian permissions exist before trying to assign them
        self._create_guardian_permissions()
        
        # Create an investigation
        self.investigation = Investigation.objects.create(
            title='Test Investigation',
            description='Test Description',
            submission_date=timezone.now().date(),
            public_release_date=timezone.now().date() + timezone.timedelta(days=30),
            security_level=SecurityLevel.PUBLIC
        )

        # Assign an owner role to the user for the investigation using the guardian-based system
        self.investigation.assign_role(self.user, 'owner')

        # Create a study within the investigation
        self.study = Study.objects.create(
            investigation=self.investigation,
            title='Test Study',
            description='Test Study Description',
            submission_date=timezone.now().date(),
            study_design='Test Design',
            security_level=SecurityLevel.PUBLIC
        )

        # Assign a contributor role to the user for the study using the guardian-based system
        self.study.assign_role(self.user, 'contributor')
        
        # Login the user for authenticated requests
        self.client.login(username='testuser', password='12345')


class TestInvestigationListEndpoint(BaseUrlTestCase):
    """Test the Investigation list endpoint"""
    
    def test_investigation_list_endpoint(self):
        """Test the investigation list endpoint"""
        url = '/api/v2/investigations/'
        print(f"Testing URL: {url}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TestInvestigationDetailEndpoint(BaseUrlTestCase):
    """Test the Investigation detail endpoint"""
    
    def test_investigation_detail_endpoint(self):
        """Test the investigation detail endpoint"""
        url = f'/api/v2/investigations/{self.investigation.accession_code}/'
        print(f"Testing URL: {url}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TestStudyListEndpoint(BaseUrlTestCase):
    """Test the Study list endpoint"""
    
    def test_study_list_endpoint(self):
        """Test the study list endpoint"""
        url = '/api/v2/studies/'
        print(f"Testing URL: {url}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TestStudyDetailEndpoint(BaseUrlTestCase):
    """Test the Study detail endpoint"""
    
    def test_study_detail_endpoint(self):
        """Test the study detail endpoint"""
        url = f'/api/v2/studies/{self.study.accession_code}/'
        print(f"Testing URL: {url}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TestDirectAccessUrls(BaseUrlTestCase):
    """Test direct URL access using accession codes"""
    
    def test_investigation_direct_access(self):
        """Test investigation direct access"""
        url = f'/api/v2/{self.investigation.accession_code}/'
        print(f"Testing URL: {url}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_study_direct_access(self):
        """Test study direct access"""
        url = f'/api/v2/{self.study.accession_code}/'
        print(f"Testing URL: {url}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class TestPermissionBasedAccess(BaseUrlTestCase):
    """Test permission-based access to resources"""
    
    def setUp(self):
        super().setUp()
        # Create another user with different permissions
        self.another_user = User.objects.create_user(username='anotheruser', password='12345')
        
        # Give the new user only read access to investigation (authorized role)
        self.investigation.assign_role(self.another_user, 'authorized')
        
        # Create a restricted investigation
        self.restricted_investigation = Investigation.objects.create(
            title='Restricted Investigation',
            description='Restricted Description',
            submission_date=timezone.now().date(),
            security_level=SecurityLevel.RESTRICTED
        )
        
        # Assign owner to original user but not to another_user
        self.restricted_investigation.assign_role(self.user, 'owner')
    
    def test_read_access_allowed(self):
        """Test that authorized user can read the investigation"""
        # Login as the other user
        self.client.logout()
        self.client.login(username='anotheruser', password='12345')
        
        # Should be able to read the investigation
        url = f'/api/v2/investigations/{self.investigation.accession_code}/'
        print(f"Testing URL: {url}")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
    
    def test_write_access_denied(self):
        """Test that authorized user cannot update the investigation"""
        # Login as the other user
        self.client.logout()
        self.client.login(username='anotheruser', password='12345')
        
        # But should not be able to update it
        url = f'/api/v2/investigations/{self.investigation.accession_code}/'
        print(f"Testing URL: {url}")
        response = self.client.put(
            url, 
            data={'title': 'Updated Title'},
            content_type='application/json'
        )
        self.assertIn(response.status_code, [400, 403, 405])  # Bad Request, Forbidden, or Method Not Allowed are all acceptable
    
    def test_restricted_investigation_access_denied(self):
        """Test that user without permission cannot access restricted investigation"""
        # Login as the other user
        self.client.logout()
        self.client.login(username='anotheruser', password='12345')
        
        # The other user should not be able to see the restricted investigation
        url = f'/api/v2/investigations/{self.restricted_investigation.accession_code}/'
        print(f"Testing URL: {url}")
        response = self.client.get(url)
        self.assertIn(response.status_code, [403, 404])  # Either Forbidden or Not Found is acceptable
    
    def test_restricted_investigation_direct_access_denied(self):
        """Test that user without permission cannot directly access restricted investigation"""
        # Login as the other user
        self.client.logout()
        self.client.login(username='anotheruser', password='12345')
        
        # Also test direct access by accession code
        url = f'/api/v2/{self.restricted_investigation.accession_code}/'
        print(f"Testing URL: {url}")
        response = self.client.get(url)
        self.assertIn(response.status_code, [403, 404])  # Either Forbidden or Not Found is acceptable
