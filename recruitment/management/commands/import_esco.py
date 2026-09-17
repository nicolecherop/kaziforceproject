import csv
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from recruitment.models import Skill, Occupation
from recruitment.matching import clear_taxonomy_cache


class Command(BaseCommand):
    help = 'Import official English ESCO skills and optional occupations CSV files.'

    def add_arguments(self, parser):
        parser.add_argument('skills_csv', type=Path)
        parser.add_argument('--occupations', type=Path)
        parser.add_argument('--esco-version', required=True)

    def handle(self, **options):
        for model, source in [(Skill, options['skills_csv']), (Occupation, options.get('occupations'))]:
            if not source:
                continue
            try:
                with source.open(encoding='utf-8-sig', newline='') as stream:
                    reader = csv.DictReader(stream)
                    if not {'conceptUri', 'preferredLabel'}.issubset(reader.fieldnames or []):
                        raise CommandError('CSV must contain conceptUri and preferredLabel columns from ESCO.')
                    objects = []
                    for row in reader:
                        uri, label = row['conceptUri'].strip(), row['preferredLabel'].strip()
                        kind = 'skill' if model is Skill else 'occupation'
                        if not uri.startswith(f'http://data.europa.eu/esco/{kind}/') or not label:
                            raise CommandError(f'Invalid ESCO {kind} URI or empty label.')
                        values = dict(uri=uri, preferred_label=label, alternative_labels=row.get('altLabels', ''), version=options['esco_version'])
                        if model is Skill:
                            values['description'] = row.get('description', '')
                        objects.append(model(**values))
                fields = ['preferred_label', 'alternative_labels', 'version'] + (['description'] if model is Skill else [])
                with transaction.atomic():
                    model.objects.bulk_create(objects, update_conflicts=True, unique_fields=['uri'], update_fields=fields, batch_size=500)
                clear_taxonomy_cache()
                self.stdout.write(self.style.SUCCESS(f'Imported {len(objects)} {model.__name__.lower()} records.'))
                self.stdout.write('Restart any running web-server processes after a catalogue import to refresh their ESCO cache.')
            except (OSError, csv.Error) as exc:
                raise CommandError(f'Could not read ESCO CSV: {source.name}') from exc
