"""Evaluate against supplied human labels; never invent research results."""
import csv
import json
import math
from pathlib import Path
from time import perf_counter
from statistics import mean
from django.core.management.base import BaseCommand, CommandError
from recruitment.matching import MatchingEngine
from recruitment.models import CandidateProfile, Job


class Command(BaseCommand):
    help = 'Measure Precision@10, NDCG@10, threshold accuracy, skill-gap F1 and response time from a labelled CSV.'

    def add_arguments(self, parser):
        parser.add_argument('labels', type=Path)
        parser.add_argument('--threshold', type=float, default=50)
        parser.add_argument('--output', type=Path, default=Path('docs/evaluation-results.json'))

    def handle(self, **options):
        if not 0 <= options['threshold'] <= 100:
            raise CommandError('Threshold must be between 0 and 100.')
        with options['labels'].open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        required = {'job_id', 'candidate_id', 'relevance', 'missing_skill_uris'}
        if not rows or not required.issubset(rows[0]):
            raise CommandError('CSV requires job_id,candidate_id,relevance,missing_skill_uris. Use | between URIs; use [] for no gaps.')
        grouped, seen = {}, set()
        for row in rows:
            try:
                job_id, candidate_id, relevance = int(row['job_id']), int(row['candidate_id']), int(row['relevance'])
            except ValueError as exc:
                raise CommandError('IDs and relevance must be integers.') from exc
            if relevance not in (0, 1, 2, 3) or (job_id, candidate_id) in seen:
                raise CommandError('Relevance must be 0..3; each candidate-job pair must occur once.')
            if not row['missing_skill_uris'].strip():
                raise CommandError('Skill-gap labels are required; [] explicitly means no missing skills.')
            seen.add((job_id, candidate_id))
            grouped.setdefault(job_id, {})[candidate_id] = row
        engine = MatchingEngine()
        per_job, accuracy, gap_tp, gap_fp, gap_fn = [], [], 0, 0, 0
        for job_id, labels in grouped.items():
            try:
                job = Job.objects.get(pk=job_id)
            except Job.DoesNotExist as exc:
                raise CommandError(f'Job {job_id} does not exist.') from exc
            profiles = list(CandidateProfile.objects.filter(user_id__in=labels).select_related('user'))
            if len(profiles) != len(labels):
                raise CommandError(f'A candidate profile is missing for job {job_id}.')
            start = perf_counter()
            results = engine.rank([job], profiles, persist=False)
            elapsed = (perf_counter() - start) * 1000
            grades = [int(labels[r['candidate'].user_id]['relevance']) for r in results]
            top = grades[:10]
            dcg = lambda values: sum((2 ** relevance - 1) / math.log2(i + 2) for i, relevance in enumerate(values))
            ideal = dcg(sorted(grades, reverse=True)[:10])
            for result in results:
                label = labels[result['candidate'].user_id]
                accuracy.append((result['score'] >= options['threshold']) == (int(label['relevance']) > 0))
                expected = set() if label['missing_skill_uris'].strip() == '[]' else set(label['missing_skill_uris'].split('|'))
                predicted = {skill['uri'] for skill in result['missing_skills']}
                gap_tp += len(predicted & expected)
                gap_fp += len(predicted - expected)
                gap_fn += len(expected - predicted)
            per_job.append({'job_id': job_id, 'candidates': len(results), 'precision_at_10': sum(g > 0 for g in top) / 10,
                'ndcg_at_10': dcg(top) / ideal if ideal else 0, 'response_ms': round(elapsed, 2),
                'ranked_candidate_ids': [r['candidate'].user_id for r in results[:10]], 'scores': [r['score'] for r in results[:10]]})
        denominator = 2 * gap_tp + gap_fp + gap_fn
        report = {'label_source': options['labels'].name, 'pairs': len(rows), 'threshold': options['threshold'],
            'threshold_accuracy': mean(accuracy), 'mean_precision_at_10': mean(r['precision_at_10'] for r in per_job),
            'mean_ndcg_at_10': mean(r['ndcg_at_10'] for r in per_job),
            'skill_gap_micro_f1': 2 * gap_tp / denominator if denominator else 1,
            'mean_response_ms': mean(r['response_ms'] for r in per_job), 'per_job': per_job,
            'limitations': 'Metrics describe only the supplied labelled pool. Precision@10 uses denominator 10 even for smaller pools. Relevant means grade > 0. UAT requires actual participants.'}
        options['output'].parent.mkdir(parents=True, exist_ok=True)
        options['output'].write_text(json.dumps(report, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Evaluation saved to {options["output"]}.'))
