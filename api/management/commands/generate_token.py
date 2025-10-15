from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Generate or retrieve API token for a user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to generate token for')
        parser.add_argument(
            '--regenerate',
            action='store_true',
            help='Delete existing token and generate a new one',
        )

    def handle(self, *args, **options):
        username = options['username']
        regenerate = options['regenerate']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User "{username}" does not exist')
            )
            return

        if regenerate:
            # Delete existing token if it exists
            Token.objects.filter(user=user).delete()
            token, created = Token.objects.get_or_create(user=user)
            self.stdout.write(
                self.style.SUCCESS(f'New token generated for user "{username}":')
            )
        else:
            # Get or create token
            token, created = Token.objects.get_or_create(user=user)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Token created for user "{username}":')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Existing token for user "{username}":')
                )

        self.stdout.write(self.style.WARNING(f'\n{token.key}\n'))
        self.stdout.write(
            self.style.SUCCESS(f'\nUse this token in API requests:')
        )
        self.stdout.write(f'Authorization: Token {token.key}')
