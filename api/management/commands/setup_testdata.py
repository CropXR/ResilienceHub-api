from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from api.models import (
    Investigation,
    SecurityLevel,
    UserRole,
)


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
        
        # Create users for different roles
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
    def create_investigations(self, users):
        """Create investigations with different security levels and permissions"""
        self.stdout.write('\nCreating investigations...')
        
        investigations = []
        for level in SecurityLevel.choices:
            # Create an investigation for each security level
            investigation = Investigation.objects.create(
                title=f"{level[1]} Security Investigation",
                description=f"An investigation with {level[1]} security level",
                submission_date=timezone.now().date(),
                public_release_date=timezone.now().date() + timezone.timedelta(days=30),
                security_level=level[0]
            )
            
            # Assign an owner for the investigation
            investigation.assign_role(users['owner_user'], UserRole.OWNER)
            
            # Optionally add a contributor
            investigation.assign_role(users['contributor_user'], UserRole.CONTRIBUTOR)
            
            investigations.append(investigation)
            self.stdout.write(f'  Created {level[1]} investigation: {investigation.accession_code}')
        
        return investigations

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\nStarting database population...'))
        self.stdout.write('=' * 50)
        
        try:
            # Create users
            users = self.create_users()
            
            # Create investigations
            investigations = self.create_investigations(users)
            
            self.stdout.write(self.style.SUCCESS('\nDatabase populated successfully!'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error populating database: {str(e)}'))