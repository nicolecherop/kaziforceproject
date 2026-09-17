import nltk
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Download NLTK English stopwords and WordNet into the project.'

    def handle(self, **options):
        target = settings.BASE_DIR / 'nltk_data'
        target.mkdir(exist_ok=True)
        for resource in ['stopwords', 'wordnet']:
            if not nltk.download(resource, download_dir=str(target), quiet=True):
                raise CommandError(f'Could not download {resource}. Check your connection and retry.')
        self.stdout.write(self.style.SUCCESS('NLTK resources are ready.'))
