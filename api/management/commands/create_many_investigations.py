from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from api.models import (
    SecurityLevel,
    InvestigationPermission,
    StudyPermission
)
from api.models import UserRole, Investigation, Study, Assay


class Command(BaseCommand):
    help = 'Populates the database with test data including users and research entities'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbosity = 1

    @transaction.atomic
    def create_users(self):
        """Create test users with different roles"""
        self.stdout.write('\nCreating users...')
        
        users = {}
        
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
            admin_user.set_password('adminpass123')
            admin_user.save()
            self.stdout.write(f'  Created admin user: admin (password: adminpass123)')
        users['admin'] = admin_user
        
        # Create users for each role
        user_configs = [
            ('guest_user', False, False),
            ('internal_user', True, False),
            ('authorized_user', False, False),
            ('contributor_user', False, False),
            ('owner_user', False, False),
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
                user.set_password('userpass123')
                user.save()
                self.stdout.write(f'  Created user: {username} (password: userpass123)')
            users[username] = user
        
        return users

    @transaction.atomic
    def create_research_entities(self, users):
        """Create test research entities with different security levels"""
        self.stdout.write('\nCreating research entities...')
        
        owner_user = users['owner_user']
        contributor_user = users['contributor_user']
        authorized_user = users['authorized_user']
        
        for i in range(1, 41):
            # Create investigation with its own security level
            inv_security = SecurityLevel.PUBLIC if i % 4 == 0 else (
                SecurityLevel.INTERNAL if i % 4 == 1 else (
                    SecurityLevel.RESTRICTED if i % 4 == 2 else SecurityLevel.CONFIDENTIAL
                )
            )
            
            # Create investigation
            inv = Investigation.objects.create(
                title=f'{inv_security} investigation {i}',
                description=f'{inv_security} investigation {i}',
                security_level=inv_security,
                submission_date=timezone.now().date(),
                public_release_date=(timezone.now() + timezone.timedelta(days=365)).date()
            )
            
            # Assign owner and contributor roles
            inv.assign_role(owner_user, UserRole.OWNER)
            inv.assign_role(contributor_user, UserRole.CONTRIBUTOR)
            inv.assign_role(authorized_user, UserRole.VIEWER)
            
            # Create studies for this investigation
            for j in range(1, 31):
                # Create study with its own independent security level
                study_security = SecurityLevel.PUBLIC if j % 4 == 0 else (
                    SecurityLevel.INTERNAL if j % 4 == 1 else (
                        SecurityLevel.RESTRICTED if j % 4 == 2 else SecurityLevel.CONFIDENTIAL
                    )
                )
                
                # Create study
                study = Study.objects.create(
                    investigation=inv,
                    title=f'{study_security} study {j} of {inv_security} investigation {i}',
                    study_label=f'S{j}',
                    description=f'{study_security} study {j} in {inv_security.lower()} investigation {i}',
                    submission_date=timezone.now().date(),
                    study_design='Randomized Control Trial',
                    security_level=study_security
                )
                
                # Assign study roles
                study.assign_role(owner_user, UserRole.OWNER)
                study.assign_role(contributor_user, UserRole.CONTRIBUTOR)
                study.assign_role(authorized_user, UserRole.VIEWER)
                
                # Create assays for this study
                for k in range(1, 21):
                    assay = Assay.objects.create(
                        study=study,
                        measurement_type='genomics',
                        description=f'Assay {k} for {study_security.lower()} study {j} of {inv_security.lower()} investigation {i}'
                    )
                
                # Logging progress
                if j % 10 == 0:
                    self.stdout.write(f'  Created {j} studies for investigation {i}')
        
        self.stdout.write(f'  Created 40 investigations with related studies and assays')

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\nStarting database population...'))
        self.stdout.write('=' * 50)
        
        try:
            # First create users
            users = self.create_users()
            
            # Then create research entities using those users
            self.create_research_entities(users)
            
            self.stdout.write(self.style.SUCCESS('\nDatabase population completed successfully!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nError during database population: {str(e)}'))
            raise