"""Interpretable information retrieval; no supervised model or training dataset."""

import math

from django.db.models import prefetch_related_objects
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..models import JobRequirement, MatchResult
from .queries import eligible_profiles, open_jobs
from .taxonomy import load_taxonomy


class MatchingEngine:
    def __init__(self):
        self.taxonomy = load_taxonomy()

    def rank(self, jobs, profiles, persist=True, ranking_context='candidate ranking'):
        jobs, profiles = list(jobs), list(profiles)
        if not jobs or not profiles:
            return []
        prefetch_related_objects(jobs, 'occupation')
        prefetch_related_objects(profiles, 'user')

        requirements_by_job = {job.pk: {} for job in jobs}
        for requirement in JobRequirement.objects.filter(job__in=jobs).select_related('skill'):
            requirements_by_job[requirement.job_id][requirement.skill_id] = (
                requirement.skill,
                requirement.priority,
                requirement.essential,
            )

        profile_data = [self.taxonomy.extract(profile.matching_text()) for profile in profiles]
        job_data, requirements = [], []
        for job in jobs:
            tokens, inferred = self.taxonomy.extract(job.matching_text())
            job_requirements = requirements_by_job[job.pk]
            for primary_key in inferred:
                job_requirements.setdefault(
                    primary_key,
                    (self.taxonomy.skills[primary_key], 1, False),
                )
            tokens = list(tokens)
            for skill, _, _ in job_requirements.values():
                marker = self.taxonomy.marker(skill)
                if marker not in tokens:
                    tokens.append(marker)
            if job.occupation_id:
                tokens += self.taxonomy.extract(job.occupation.preferred_label)[0]
            job_data.append(tokens)
            requirements.append(job_requirements)

        corpus = [data[0] for data in profile_data] + job_data
        if any(corpus):
            vectorizer = TfidfVectorizer(analyzer=lambda document: document, sublinear_tf=True)
            vectors = vectorizer.fit_transform(corpus)
            features = vectorizer.get_feature_names_out()
        else:
            vectors, features = None, []

        results = []
        for job_index, job in enumerate(jobs):
            job_requirements = requirements[job_index]
            if vectors is not None:
                weights = [1.0] * len(features)
                priority = {
                    self.taxonomy.marker(skill): weight
                    for skill, weight, _ in job_requirements.values()
                }
                for feature_index, feature in enumerate(features):
                    weights[feature_index] = math.sqrt(priority.get(feature, 1))
                candidates = vectors[:len(profiles)].multiply(weights).tocsr()
                target = vectors[len(profiles) + job_index].multiply(weights).tocsr()
                scores = cosine_similarity(candidates, target).ravel()

            for profile_index, profile in enumerate(profiles):
                score = (
                    max(0.0, min(100.0, float(scores[profile_index]) * 100))
                    if vectors is not None
                    else 0.0
                )
                matched, missing = [], []
                for primary_key, (skill, weight, essential) in job_requirements.items():
                    detail = {
                        'label': skill.preferred_label,
                        'uri': skill.uri,
                        'priority': weight,
                        'essential': essential,
                    }
                    destination = matched if primary_key in profile_data[profile_index][1] else missing
                    destination.append(detail)

                top_terms = []
                if vectors is not None:
                    overlap = candidates[profile_index].multiply(target).tocoo()
                    top_terms = [
                        {
                            'term': self.taxonomy.labels.get(features[index], features[index]),
                            'weight': round(float(value), 5),
                        }
                        for index, value in sorted(
                            zip(overlap.col, overlap.data), key=lambda item: -item[1]
                        )[:8]
                    ]
                explanation = {
                    'method': 'NLTK + ESCO + weighted TF-IDF cosine',
                    'top_terms': top_terms,
                    'corpus_size': len(corpus),
                    'profile_updated': profile.updated_at.isoformat(),
                    'job_updated': job.updated_at.isoformat(),
                    'esco_versions': self.taxonomy.versions,
                    'note': 'Similarity is a decision-support score, not a probability of hiring. Missing skills mean no evidence found in the supplied text.',
                }
                values = {
                    'score': round(score, 2),
                    'matched_skills': matched,
                    'missing_skills': missing,
                    'explanation': explanation,
                }
                results.append({'candidate': profile, 'job': job, **values})

        results.sort(key=lambda result: (-result['score'], result['job'].pk, result['candidate'].pk))
        ranks, snapshots = {}, []
        for result in results:
            group = (
                result['candidate'].pk
                if ranking_context == 'job recommendations'
                else result['job'].pk
            )
            ranks[group] = ranks.get(group, 0) + 1
            result['explanation']['rank'] = ranks[group]
            result['explanation']['ranking_context'] = ranking_context
            if persist:
                snapshots.append(
                    MatchResult(
                        candidate=result['candidate'].user,
                        job=result['job'],
                        **{
                            key: result[key]
                            for key in [
                                'score',
                                'matched_skills',
                                'missing_skills',
                                'explanation',
                            ]
                        },
                    )
                )
        if snapshots:
            MatchResult.objects.bulk_create(
                snapshots,
                update_conflicts=True,
                unique_fields=['candidate', 'job'],
                update_fields=[
                    'score',
                    'matched_skills',
                    'missing_skills',
                    'explanation',
                    'calculated_at',
                ],
                batch_size=500,
            )
        return results

    def candidates(self, job):
        return self.rank([job], eligible_profiles(job))[:10]

    def recommendations(self, profile):
        jobs = open_jobs().select_related('occupation')
        return self.rank(jobs, [profile], ranking_context='job recommendations')[:10]
