# isa_api/tests/v1/test_urls.py
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
    ROLE_PERMISSIONS
)
from django.utils import timezone

class UrlAccessTest(TestCase):
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

        # Assign an owner role to the user for the investigation using the new guardian-based system
        self.investigation.assign_role(self.user, 'owner')

        # Create a study within the investigation
        self.study = Study.objects.create(
            investigation=self.investigation,
            title='Test Study',
            description='Test Study Description',
            study_label='STUDY1',
            submission_date=timezone.now().date(),
            study_design='Test Design',
            security_level=SecurityLevel.PUBLIC
        )

        # Assign a contributor role to the user for the study using the new guardian-based system
        self.study.assign_role(self.user, 'contributor')

        # Create an assay within the study
        self.assay = Assay.objects.create(
            study=self.study,
            measurement_type='genomics',
            description='Test Assay Description'
        )

        # Login the user for authenticated requests
        self.client.login(username='testuser', password='12345')
        
    def _create_guardian_permissions(self):
        """
        Create the necessary permissions for guardian in the test database.
        We only need to create custom permissions - Django's defaults are already there.
        """
        # Create custom permissions for Investigation model
        investigation_ct = ContentType.objects.get_for_model(Investigation)
        
        # Use get_or_create to avoid duplicate permission errors
        try:
            Permission.objects.get_or_create(
                codename=f'{PERMISSION_MANAGE_PERMS}_investigation',
                defaults={'name': f'Can {PERMISSION_MANAGE_PERMS} investigation', 'content_type': investigation_ct}
            )
        except IntegrityError:
            # Permission already exists, just retrieve it
            pass
            
        # Create custom permissions for Study model
        study_ct = ContentType.objects.get_for_model(Study)
        try:
            Permission.objects.get_or_create(
                codename=f'{PERMISSION_MANAGE_PERMS}_study',
                defaults={'name': f'Can {PERMISSION_MANAGE_PERMS} study', 'content_type': study_ct}
            )
        except IntegrityError:
            # Permission already exists, just retrieve it
            pass

    def test_direct_urls(self):
        """Test direct URL access using accession codes"""
        # Test investigation direct access
        url = f'/api/v1/{self.investigation.accession_code}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test study direct access
        url = f'/api/v1/investigations/{self.investigation.accession_code}/studies/{self.study.accession_code}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test assay direct access
        url = f'/api/v1/investigations/{self.investigation.accession_code}/studies/{self.study.accession_code}/assays/{self.assay.accession_code}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_nested_urls(self):
        """Test nested URL access patterns"""
        # Test studies within an investigation
        url = f'/api/v1/investigations/{self.investigation.accession_code}/studies/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Test assays within a study
        url = f'/api/v1/investigations/{self.investigation.accession_code}/studies/{self.study.accession_code}/assays/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_permission_based_access(self):
        """Test that permissions affect access properly"""
        # Create another user with different permissions
        another_user = User.objects.create_user(username='anotheruser', password='12345')
        
        # Give the new user only read access to investigation (authorized role)
        self.investigation.assign_role(another_user, 'authorized')
        
        # Login as the new user
        self.client.logout()
        self.client.login(username='anotheruser', password='12345')
        
        # Should be able to read the investigation
        url = f'/api/v1/{self.investigation.accession_code}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # But should not be able to update it
        response = self.client.put(
            url, 
            data={'title': 'Updated Title'},
            content_type='application/json'
        )
        self.assertIn(response.status_code, [403, 405])  # Either Forbidden or Method Not Allowed is acceptable
        
        # Test that security level restrictions work as expected
        # Create a restricted investigation
        restricted_investigation = Investigation.objects.create(
            title='Restricted Investigation',
            description='Restricted Description',
            submission_date=timezone.now().date(),
            security_level=SecurityLevel.RESTRICTED
        )
        
        # Assign owner to original user but not to another_user
        restricted_investigation.assign_role(self.user, 'owner')
        
        # The other user should not be able to see the restricted investigation
        url = f'/api/v1/{restricted_investigation.accession_code}/'
        response = self.client.get(url)
        self.assertIn(response.status_code, [403, 404])  # Either Forbidden or Not Found is acceptable