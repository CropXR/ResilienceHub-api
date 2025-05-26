from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from api.database_models.models import (
    SecurityLevel
)
from api.database_models.models import Investigation, Study, Assay


class Command(BaseCommand):
    help = 'Creates comprehensive test data with investigations, studies, and assays'

    @transaction.atomic
    def create_users(self):
        """Create test users with different roles"""
        self.stdout.write('\nCreating users...')
        
        users = {'project_a': {}, 'project_b': {}}
        
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
            self.stdout.write(f'  Created admin user: admin (password: pass123)')
        
        # Roles to create
        roles = [
            ('owner', 'Owner', 'owner'),
            ('contributor', 'Contributor', 'contributor'),
            ('viewer', 'Viewer', 'authorized')
        ]
        
        # Create users for both projects
        for project_prefix in ['project_a', 'project_b']:
            for role_type, role_desc, role_key in roles:
                username = f'{project_prefix}_{role_type}'
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': f'{username}@example.com',
                        'first_name': f'{project_prefix.split("_")[0].capitalize()} {role_desc}',
                        'is_staff': role_type in ['owner', 'contributor']
                    }
                )
                if created:
                    user.set_password('pass123')
                    user.save()
                    self.stdout.write(f'  Created user: {username} (password: pass123)')
                
                users[project_prefix][username] = {
                    'user': user,
                    'role': role_key
                }
        
        return users, admin_user

    @transaction.atomic
    def create_project_structure(self, project_name, users, admin_user):
        """Create investigations, studies, and assays for a project"""
        self.stdout.write(f'\nCreating structure for {project_name}...')
        
        investigations = []
        
        # Create investigation for each security level
        for security_level, _ in SecurityLevel.choices:
            investigation = Investigation.objects.create(
                title=f"{project_name} - {security_level.capitalize()} Security Investigation",
                description=f"An investigation with {security_level} security level for {project_name}",
                submission_date=timezone.now().date(),
                public_release_date=timezone.now().date() + timezone.timedelta(days=30),
                security_level=security_level
            )
            
            # Assign roles for this investigation
            for username, user_data in users.items():
                investigation.assign_role(user_data['user'], user_data['role'])
            
            # Ensure admin has full access
            investigation.assign_role(admin_user, 'owner')
            
            self.stdout.write(f'  Created {security_level} investigation: {investigation.accession_code}')
            investigations.append(investigation)
            
            # Create studies for this investigation
            for study_security_level, _ in SecurityLevel.choices:
                study = Study.objects.create(
                    investigation=investigation,
                    title=f"{investigation.title} - Study with {study_security_level} Security",
                    description=f"A study with {study_security_level} security level",
                    submission_date=timezone.now().date(),
                    security_level=study_security_level
                )
                
                # Assign roles for the study
                for username, user_data in users.items():
                    study.assign_role(user_data['user'], user_data['role'])
                
                # Ensure admin has full access
                study.assign_role(admin_user, 'owner')
                
                self.stdout.write(f'    Created {study_security_level} study: {study.accession_code}')
                
                # Create an assay for this study
                assay = Assay.objects.create(
                    study=study,
                    title=f"{study.title} - Assay",
                    description=f"An assay for {study.title}",
                    measurement_type="Genomics"
                )
                
                self.stdout.write(f'      Created assay: {assay.accession_code}')
        
        return investigations

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\nStarting setup of investigations, studies, and assays...'))
        
        try:
            # Create users for both projects
            users, admin_user = self.create_users()
            
            # Create structure for Project A
            project_a_investigations = self.create_project_structure('Project A', users['project_a'], admin_user)
            
            # Create structure for Project B
            project_b_investigations = self.create_project_structure('Project B', users['project_b'], admin_user)
            
            self.stdout.write(self.style.SUCCESS('\nSetup completed successfully!'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during setup: {str(e)}'))