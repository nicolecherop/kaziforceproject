from django.db import connection
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Verify PostgreSQL connectivity without printing credentials.'

    def handle(self, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_database(), version()')
                database, version = cursor.fetchone()
                tls = connection.connection.pgconn.ssl_in_use
        except Exception as exc:
            # Some driver errors contain connection details. Do not echo them.
            raise CommandError('Could not connect to PostgreSQL. Check DATABASE_URL, network access and Neon project status. Credentials were not logged.') from None
        self.stdout.write(self.style.SUCCESS(f'Connected to {database}. {version.split(",")[0]}. Client TLS: {tls}'))
