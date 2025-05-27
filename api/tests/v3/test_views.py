from django.test import TestCase

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.utils import timezone

from api.choices import SecurityLevel
from api.models import Investigation
from api.permissions import PERMISSION_MANAGE_PERMS

from api.tests.helpers import create_permission_safely


# tested
    # list inv method works
    # list inv implements permission restrictions

# to test
    # inv other methods (?) work
    # inv other methods (?) implement permission restrictions

    # html view implement permissions


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

    def setUp(self):
        self.base_url = '/api/v3'

        # Create a user for permissions
        self.user = User.objects.create_user(username='testuser', password='12345')

        # Ensure guardian permissions exist before trying to assign them
        self._create_guardian_permissions()

        # Create an investigations

        self.investigation = Investigation.objects.create(
            title='Test Investigation',
            description='Test Description',
            submission_date=timezone.now().date(),
            public_release_date=timezone.now().date() + timezone.timedelta(days=30),
            security_level=SecurityLevel.PUBLIC
        )

        # Assign an owner role to the user for the investigation using the guardian-based system
        self.investigation.assign_role(self.user, 'owner')


class TestInvestigationViewSetPermissions(BaseUrlTestCase):
    """
    Test permission-based access to resources.
    All combinations of roles and permissions should be covered in test_permission_matrix.
    This test checks if these permissions are properly implemented in the views.
    """

    def setUp(self):
        super().setUp()
        # Create another user with different permissions
        self.another_user = User.objects.create_user(username='anotheruser', password='12345')
        self.url = f'{self.base_url}/investigations/'


    def test_owner_can_list_public_investigation(self):
        """Test that authorized user can read the investigation"""
        self.client.login(username='testuser', password='12345')

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        self.assertIn(
            self.investigation.title,
            [investigation['title'] for investigation in response.json()['results']]
        )

    def test_other_user_can_list_public_investigation(self):
        """Test that other user can list the public investigation"""
        self.client.login(username='anotheruser', password='12345')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            self.investigation.title,
            [investigation['title'] for investigation in response.json()['results']]
        )

    def test_contributor_can_list_restricted_investigation(self):
        # Create a restricted investigation
        self.investigation = Investigation.objects.create(
            title='Restricted Investigation',
            description='Restricted Description',
            submission_date=timezone.now().date(),
            security_level=SecurityLevel.RESTRICTED
        )
        self.investigation.assign_role(self.another_user, 'authorized')

        self.client.login(username='anotheruser', password='12345')

        # Should be able to read the investigation
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        results = response.json()['results']
        self.assertIn(
            self.investigation.title,
            [investigation['title'] for investigation in results]
        )

    def test_restricted_investigation_no_listed_to_other_user(self):
        # Create a restricted investigation
        self.investigation = Investigation.objects.create(
            title='Restricted Investigation',
            description='Restricted Description',
            submission_date=timezone.now().date(),
            security_level=SecurityLevel.RESTRICTED
        )

        self.client.login(username='anotheruser', password='12345')

        # Should be able to read the investigation
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertNotIn(
            self.investigation.title,
            [investigation.title() for investigation in response.json()['results']]
        )

    # add other InvestigationViewSet operations


class TestCatalogueHtmlViewPermissions(BaseUrlTestCase):

    def setUp(self):
        super().setUp()
        self.url = f'{self.base_url}/catalogue/'

    def test_catalogue_html_can_render(self):
        self.client.login(username=self.user.username, password='12345')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, self.investigation.title)
