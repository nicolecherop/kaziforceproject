from datetime import timedelta

from django.utils import timezone

from ..matching import MatchingEngine, Taxonomy, preprocess
from ..models import CandidateProfile, Job, JobRequirement, MatchResult, Skill, User
from .base import BaseCase


class MatchingTests(BaseCase):
    def test_requirements_query_count_does_not_grow_with_jobs(self):
        for index in range(4):
            job = Job.objects.create(
                recruiter=self.recruiter,
                title=f'Role {index}',
                company='Test',
                location='Nairobi',
                employment_type='full_time',
                description='Python',
                status='open',
            )
            JobRequirement.objects.create(job=job, skill=self.python, priority=3)
        jobs = list(Job.objects.select_related('occupation'))
        engine = MatchingEngine()
        with self.assertNumQueries(1):
            results = engine.rank(jobs, [self.profile], persist=False)
        self.assertEqual(len(results), 5)

    def test_taxonomy_is_reused_without_database_reload(self):
        first = MatchingEngine()
        with self.assertNumQueries(0):
            second = MatchingEngine()
        self.assertIs(first.taxonomy, second.taxonomy)

    def test_admin_taxonomy_change_invalidates_cache(self):
        first = MatchingEngine()
        self.python.alternative_labels = 'SnakeCode'
        self.python.save()
        second = MatchingEngine()
        self.assertIsNot(first.taxonomy, second.taxonomy)
        self.assertIn(self.python.pk, second.taxonomy.extract('SnakeCode')[1])

    def test_identical_profile_scores_100(self):
        results = MatchingEngine().rank([self.job], [self.profile])
        self.assertAlmostEqual(results[0]['score'], 100, places=1)
        self.assertEqual(len(results[0]['matched_skills']), 2)
        self.assertEqual(results[0]['missing_skills'], [])
        self.assertEqual(MatchResult.objects.count(), 1)
        self.assertEqual(MatchResult.objects.get().explanation['rank'], 1)

    def test_synonyms_share_a_canonical_feature(self):
        taxonomy = Taxonomy(Skill.objects.all())
        self.assertEqual(
            taxonomy.extract('Py Structured Query Language'),
            taxonomy.extract('Python SQL'),
        )

    def test_word_boundaries_prevent_java_javascript_match(self):
        _, skill_ids = Taxonomy(Skill.objects.all()).extract('JavaScript')
        self.assertNotIn(self.java.pk, skill_ids)

    def test_technical_punctuation_is_preserved(self):
        for name in ['C', 'C++', 'C#', 'R']:
            Skill.objects.create(
                uri='http://data.europa.eu/esco/skill/test-'
                + str(len(name))
                + name.replace('#', 'sharp'),
                preferred_label=name,
            )
        taxonomy = Taxonomy(Skill.objects.all())
        for name in ['C', 'C++', 'C#', 'R']:
            _, skill_ids = taxonomy.extract(name)
            labels = {taxonomy.skills[primary_key].preferred_label for primary_key in skill_ids}
            self.assertEqual(labels, {name})

    def test_priority_changes_ranking(self):
        self.profile.headline = self.profile.qualifications = ''
        self.profile.skills_text = 'Python'
        other_user = User.objects.create_user('sqlonly', email='sql@example.test')
        other_profile = CandidateProfile.objects.create(user=other_user, skills_text='SQL')
        self.job.title = self.job.qualifications = ''
        self.job.description = 'Python SQL'
        results = MatchingEngine().rank(
            [self.job], [other_profile, self.profile], persist=False
        )
        self.assertEqual(results[0]['candidate'].pk, self.profile.pk)
        self.job.requirements.filter(skill=self.python).update(priority=1)
        self.job.requirements.filter(skill=self.sql).update(priority=5)
        results = MatchingEngine().rank(
            [self.job], [other_profile, self.profile], persist=False
        )
        self.assertEqual(results[0]['candidate'].pk, other_profile.pk)

    def test_no_overlap_scores_zero_and_reports_gaps(self):
        self.profile.headline = self.profile.qualifications = ''
        self.profile.skills_text = 'pottery ceramics'
        result = MatchingEngine().rank([self.job], [self.profile])[0]
        self.assertEqual(result['score'], 0)
        self.assertEqual(len(result['missing_skills']), 2)

    def test_empty_profile_is_safe(self):
        self.profile.headline = self.profile.qualifications = self.profile.skills_text = ''
        self.assertEqual(
            MatchingEngine().rank([self.job], [self.profile])[0]['score'],
            0,
        )

    def test_rankings_are_capped_at_ten(self):
        for index in range(12):
            user = User.objects.create_user(
                f'person{index}', email=f'p{index}@example.test'
            )
            CandidateProfile.objects.create(
                user=user,
                skills_text='Python',
                discoverable=True,
            )
        self.assertEqual(len(MatchingEngine().candidates(self.job)), 10)

    def test_recommendations_exclude_closed_expired_draft(self):
        states = [
            ('closed', None),
            ('draft', None),
            ('open', timezone.localdate() - timedelta(days=1)),
        ]
        for state, deadline in states:
            Job.objects.create(
                recruiter=self.recruiter,
                title='Hidden',
                company='Test',
                location='Nairobi',
                employment_type='full_time',
                description='Python',
                status=state,
                deadline=deadline,
            )
        results = MatchingEngine().recommendations(self.profile)
        self.assertEqual([result['job'].pk for result in results], [self.job.pk])

    def test_nltk_removes_stopwords_and_lemmatises(self):
        tokens = preprocess('the skills and databases')
        self.assertNotIn('the', tokens)
        self.assertIn('skill', tokens)
        self.assertIn('database', tokens)

    def test_names_do_not_change_scores(self):
        original = MatchingEngine().rank([self.job], [self.profile])[0]['score']
        self.candidate.first_name = 'Completely Different Name'
        self.candidate.save()
        current = MatchingEngine().rank([self.job], [self.profile])[0]['score']
        self.assertEqual(current, original)
