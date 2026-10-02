from django.test import TestCase

from ..matching import clear_taxonomy_cache
from ..models import (
    CandidateProfile,
    Job,
    JobRequirement,
    RecruiterProfile,
    Skill,
    User,
)


class BaseCase(TestCase):
    def setUp(self):
        clear_taxonomy_cache()

    def tearDown(self):
        clear_taxonomy_cache()

    @classmethod
    def setUpTestData(cls):
        cls.recruiter = User.objects.create_user(
            'recruiter',
            email='recruiter@example.test',
            password='Example-pass-587!',
            role='recruiter',
        )
        cls.other = User.objects.create_user(
            'other',
            email='other@example.test',
            password='Example-pass-587!',
            role='recruiter',
        )
        RecruiterProfile.objects.create(user=cls.recruiter, company='Test Company')
        cls.candidate = User.objects.create_user(
            'candidate',
            email='candidate@example.test',
            password='Example-pass-587!',
        )
        cls.profile = CandidateProfile.objects.create(
            user=cls.candidate,
            headline='Developer',
            skills_text='Python SQL',
            qualifications='Computer science',
            discoverable=True,
        )
        cls.python = Skill.objects.create(
            uri='http://data.europa.eu/esco/skill/test-python',
            preferred_label='Python',
            alternative_labels='Py',
        )
        cls.sql = Skill.objects.create(
            uri='http://data.europa.eu/esco/skill/test-sql',
            preferred_label='SQL',
            alternative_labels='Structured Query Language',
        )
        cls.java = Skill.objects.create(
            uri='http://data.europa.eu/esco/skill/test-java',
            preferred_label='Java',
        )
        cls.job = Job.objects.create(
            recruiter=cls.recruiter,
            title='Developer',
            company='Test Company',
            location='Nairobi',
            employment_type='full_time',
            description='Python SQL',
            qualifications='Computer science',
            status='open',
        )
        JobRequirement.objects.create(job=cls.job, skill=cls.python, priority=5)
        JobRequirement.objects.create(job=cls.job, skill=cls.sql, priority=1)
