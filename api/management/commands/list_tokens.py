from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token
from django.utils import timezone


class Command(BaseCommand):
    help = 'List all API tokens'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-keys',
            action='store_true',
            help='Show full token keys (security warning: use with caution)',
        )

    def handle(self, *args, **options):
        show_keys = options['show_keys']
        tokens = Token.objects.select_related('user').all()

        if not tokens:
            self.stdout.write(
                self.style.WARNING('No API tokens found')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'\nFound {tokens.count()} API token(s):\n')
        )

        for token in tokens:
            user = token.user
            created = token.created.strftime('%Y-%m-%d %H:%M:%S')

            self.stdout.write(f'User: {user.username}')
            self.stdout.write(f'  Name: {user.get_full_name() or "N/A"}')
            self.stdout.write(f'  Email: {user.email or "N/A"}')
            self.stdout.write(f'  Created: {created}')

            if show_keys:
                self.stdout.write(
                    self.style.WARNING(f'  Token: {token.key}')
                )
            else:
                # Show only first 8 characters
                self.stdout.write(f'  Token: {token.key[:8]}...')

            self.stdout.write('')

        if not show_keys:
            self.stdout.write(
                self.style.NOTICE(
                    'Tip: Use --show-keys to display full token keys'
                )
            )
