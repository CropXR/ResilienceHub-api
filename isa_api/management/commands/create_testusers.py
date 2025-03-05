from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

class Command(BaseCommand):
    help = 'Populates the database with test users only'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbosity = 1

    @transaction.atomic
    def create_users(self):
        """Create test users with different roles"""
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
            self.stdout.write(f'  Created admin user: admin (password: password)')
        else:
            self.stdout.write(f'  Admin user already exists')
        
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
                self.stdout.write(f'  Created user: {username} (password: pass123)')
                if is_staff:
                    self.stdout.write(f'    Set as internal user (staff)')
            else:
                self.stdout.write(f'  User {username} already exists')
            
            users.append(user)
        
        return users

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\nStarting user creation...'))
        self.stdout.write('=' * 50)
        
        try:
            # Create users
            users = self.create_users()
            self.stdout.write(self.style.SUCCESS('\nUser creation completed successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nError during user creation: {str(e)}'))
            raise
    