from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from api.models import (
    Investigation, 
    Study, 
    SecurityLevel
)


class Command(BaseCommand):
    """Management command to populate the database with test data including users, investigations, and studies."""
    
    help = 'Populates the database with test users, investigations, and studies'

    def __init__(self, *args, **kwargs):
        """Initialize the command with verbosity level."""
        super().__init__(*args, **kwargs)
        self.verbosity = 1

    @transaction.atomic
    def create_users(self):
        """Create test users with different roles.
        
        Returns:
            list: List of created User objects.
        """
        self.stdout.write('\nCreating users...')
        
        users = []
        
        # Create superuser/admin
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_superuser': True,
                'is_staff': True
            }
        )
        if created:
            admin_user.set_password('pass123')
            admin_user.save()
            self.stdout.write('  Created admin user: admin (password: pass123)')
        else:
            self.stdout.write('  Admin user already exists')
        
        users.append(admin_user)
        
        # Create users for each role
        user_configs = [
            ('guest_user', False, False),      # Guest role (not staff)
            ('internal_user', True, False),    # Internal role (is_staff)
            ('authorized_user', False, False), # Will be added as authorized_user to specific resources
            ('contributor_user', False, False), # Will be added as contributor to specific resources
            ('owner_user', False, False),      # Will be added as owner to specific resources
            ('user', False, False),            # Will be added as owner to specific resources
        ]
        
        for username, is_staff, is_superuser in user_configs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@example.com',
                    'is_staff': is_staff,
                    'is_superuser': is_superuser
                }
            )
            if created:
                user.set_password('pass123')
                user.save()
                self.stdout.write('  Created user: {} (password: pass123)'.format(username))
                if is_staff:
                    self.stdout.write('    Set as internal user (staff)')
            else:
                self.stdout.write('  User {} already exists'.format(username))
            
            users.append(user)
        
        return users

    @transaction.atomic
    def create_investigations(self, users):
        """Create sample investigations with different security levels and assign roles.
        
        Args:
            users (list): List of User objects to assign roles to.
            
        Returns:
            list: List of created Investigation objects.
        """
        self.stdout.write('\nCreating investigations...')
        
        investigations = []
        
        # Find specific users by username for role assignments
        user_dict = {user.username: user for user in users}
        owner_user = user_dict.get('owner_user')
        contributor_user = user_dict.get('contributor_user')
        authorized_user = user_dict.get('authorized_user')
        internal_user = user_dict.get('internal_user')
        
        # Create investigations for each security level
        investigation_configs = [
            ('Public Research Project', 'A publicly accessible research investigation', SecurityLevel.PUBLIC, 'Dr. Sarah Johnson', 'sarah.johnson@university.edu'),
            ('Internal Company Study', 'An internal research study for company use only', SecurityLevel.INTERNAL, 'Dr. Michael Chen', 'michael.chen@company.com'),
            ('Restricted Clinical Trial', 'A restricted access clinical trial investigation', SecurityLevel.RESTRICTED, 'Dr. Emily Rodriguez', 'emily.rodriguez@hospital.org'),
            ('Confidential Drug Development', 'A confidential pharmaceutical development study', SecurityLevel.CONFIDENTIAL, 'Dr. James Wilson', 'james.wilson@pharma.com'),
        ]
        
        for title, description, security_level, pi_name, pi_email in investigation_configs:
            investigation = Investigation.objects.create(
                title=title,
                description=description,
                submission_date=timezone.now().date(),
                public_release_date=timezone.now().date() + timezone.timedelta(days=30),
                security_level=security_level,
                principal_investigator_name=pi_name,
                principal_investigator_email=pi_email
            )
            
            # Assign roles using the set_user_role method from GuardianMixin
            if owner_user:
                investigation.set_user_role(owner_user, 'owner')
            if contributor_user:
                investigation.set_user_role(contributor_user, 'contributor')
            if authorized_user:
                investigation.set_user_role(authorized_user, 'authorized')
            if internal_user:
                investigation.set_user_role(internal_user, 'internal')
            
            investigations.append(investigation)
            self.stdout.write('  Created investigation: {} ({})'.format(
                investigation.accession_code, security_level
            ))
            self.stdout.write('    Assigned roles: owner, contributor, authorized, internal')
        
        return investigations

    @transaction.atomic
    def create_studies(self, investigations, users):
        """Create sample studies linked to the investigations and assign roles.
        
        Args:
            investigations (list): List of Investigation objects to link studies to.
            users (list): List of User objects to assign roles to.
            
        Returns:
            list: List of created Study objects.
        """
        self.stdout.write('\nCreating studies...')
        
        studies = []
        
        # Find specific users by username for role assignments
        user_dict = {user.username: user for user in users}
        owner_user = user_dict.get('owner_user')
        contributor_user = user_dict.get('contributor_user')
        authorized_user = user_dict.get('authorized_user')
        internal_user = user_dict.get('internal_user')
        
        # Create 2 studies per investigation
        study_templates = [
            ('Baseline Measurements', 'Initial baseline data collection phase', None, None),  # Will inherit PI from investigation
            ('Treatment Phase', 'Active treatment and monitoring phase', 'Dr. Alex Thompson', 'alex.thompson@lab.edu'),  # Override PI
        ]
        
        for investigation in investigations:
            for study_title, study_description, study_pi_name, study_pi_email in study_templates:
                study = Study.objects.create(
                    investigation=investigation,
                    title='{} - {}'.format(investigation.title, study_title),
                    description=study_description,
                    submission_date=timezone.now().date(),
                    public_release_date=investigation.public_release_date,
                    security_level=investigation.security_level,
                    principal_investigator_name=study_pi_name,  # Will be None for baseline, set for treatment
                    principal_investigator_email=study_pi_email
                )
                
                # Assign roles using the set_user_role method from GuardianMixin
                if owner_user:
                    study.set_user_role(owner_user, 'owner')
                if contributor_user:
                    study.set_user_role(contributor_user, 'contributor')
                if authorized_user:
                    study.set_user_role(authorized_user, 'authorized')
                if internal_user:
                    study.set_user_role(internal_user, 'internal')
                
                studies.append(study)
                self.stdout.write('  Created study: {} (Investigation: {})'.format(
                    study.accession_code, investigation.accession_code
                ))
                self.stdout.write('    Assigned roles: owner, contributor, authorized, internal')
        
        return studies

    @transaction.atomic
    def handle(self, *args, **kwargs):
        """Handle the management command execution.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        self.stdout.write(self.style.SUCCESS('\nStarting database population...'))
        self.stdout.write('=' * 50)
        
        try:
            # Create users
            users = self.create_users()
            
            # Create investigations
            investigations = self.create_investigations(users)
            
            # Create studies
            studies = self.create_studies(investigations, users)
            
            self.stdout.write('=' * 50)
            self.stdout.write(self.style.SUCCESS('\nDatabase population completed successfully!'))
            self.stdout.write('Summary:')
            self.stdout.write('  - Users created: {}'.format(len(users)))
            self.stdout.write('  - Investigations created: {}'.format(len(investigations)))
            self.stdout.write('  - Studies created: {}'.format(len(studies)))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR('\nError during database population: {}'.format(str(e))))
            raise