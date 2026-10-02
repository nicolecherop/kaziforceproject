import csv
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command

from .base import BaseCase


class ManagementCommandTests(BaseCase):
    def test_esco_import_updates_existing_uri_without_breaking_requirements(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'skills.csv'
            with path.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=['conceptUri', 'preferredLabel', 'altLabels'],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        'conceptUri': self.python.uri,
                        'preferredLabel': 'Python language',
                        'altLabels': 'Python\nPy',
                    }
                )
            call_command(
                'import_esco',
                str(path),
                esco_version='1.2.0',
                stdout=StringIO(),
            )
        self.python.refresh_from_db()
        self.assertEqual(self.python.preferred_label, 'Python language')
        self.assertEqual(self.job.requirements.get(skill=self.python).priority, 5)

    def test_evaluation_outputs_metrics_for_supplied_fixture_labels(self):
        with TemporaryDirectory() as directory:
            labels = Path(directory) / 'labels.csv'
            output = Path(directory) / 'report.json'
            with labels.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                writer.writerow(
                    ['job_id', 'candidate_id', 'relevance', 'missing_skill_uris']
                )
                writer.writerow([self.job.pk, self.candidate.pk, 3, '[]'])
            call_command(
                'evaluate_matching',
                str(labels),
                output=output,
                stdout=StringIO(),
            )
            report = json.loads(output.read_text())
            self.assertEqual(report['pairs'], 1)
            self.assertEqual(report['mean_ndcg_at_10'], 1)
            self.assertEqual(report['threshold_accuracy'], 1)
            self.assertEqual(report['skill_gap_micro_f1'], 1)
