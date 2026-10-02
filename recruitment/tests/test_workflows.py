from django.test import Client
from django.urls import reverse

from ..forms import RegisterForm
from ..matching import eligible_profiles
from ..models import (
    Application,
    ApplicationEvent,
    CandidateProfile,
    Job,
    JobRequirement,
    Skill,
    User,
)
from .base import BaseCase


class WorkflowTests(BaseCase):
    def test_job_creation_persists_priority_and_owner(self):
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse('job_create'),
            {
                'title': 'New role',
                'company': 'Test Company',
                'location': 'Remote',
                'employment_type': 'contract',
                'description': 'Build with Python',
                'status': 'open',
                'requirements-TOTAL_FORMS': '1',
                'requirements-INITIAL_FORMS': '0',
                'requirements-MIN_NUM_FORMS': '0',
                'requirements-MAX_NUM_FORMS': '30',
                'requirements-0-skill': str(self.python.pk),
                'requirements-0-priority': '4',
                'requirements-0-essential': 'on',
                'recruiter': self.other.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(title='New role')
        self.assertEqual(job.recruiter, self.recruiter)
        self.assertEqual(job.requirements.get().priority, 4)

    def test_catalogue_search_requires_login_and_returns_synonyms(self):
        url = reverse('catalogue_search') + '?q=structured&kind=skill'
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.recruiter)
        self.assertEqual(
            self.client.get(url).json()['results'],
            [{'id': self.sql.pk, 'label': 'SQL'}],
        )

    def test_candidate_cannot_create_or_edit_jobs(self):
        self.client.force_login(self.candidate)
        self.assertEqual(self.client.get(reverse('job_create')).status_code, 403)
        self.assertEqual(
            self.client.post(reverse('job_edit', args=[self.job.pk]), {}).status_code,
            403,
        )

    def test_recruiter_cannot_manage_another_recruiters_job(self):
        self.client.force_login(self.other)
        for name in ['job_edit', 'ranking']:
            self.assertEqual(
                self.client.get(reverse(name, args=[self.job.pk])).status_code,
                404,
            )

    def test_duplicate_application_is_idempotent(self):
        self.client.force_login(self.candidate)
        for _ in range(2):
            self.client.post(
                reverse('apply', args=[self.job.pk]),
                {'cover_note': 'Interested'},
            )
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(ApplicationEvent.objects.count(), 1)

    def test_closed_job_cannot_receive_applications(self):
        self.job.status = 'closed'
        self.job.save()
        self.client.force_login(self.candidate)
        self.client.post(reverse('apply', args=[self.job.pk]))
        self.assertFalse(Application.objects.exists())

    def test_application_status_permissions_and_history(self):
        application = Application.objects.create(candidate=self.candidate, job=self.job)
        self.client.force_login(self.other)
        response = self.client.post(
            reverse('application_status', args=[application.pk]),
            {'status': 'shortlisted'},
        )
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.recruiter)
        self.client.post(
            reverse('application_status', args=[application.pk]),
            {'status': 'shortlisted'},
        )
        application.refresh_from_db()
        self.assertEqual(application.status, 'shortlisted')
        self.assertEqual(application.events.count(), 1)
        self.client.force_login(self.candidate)
        self.client.post(
            reverse('application_status', args=[application.pk]),
            {'status': 'hired'},
        )
        application.refresh_from_db()
        self.assertEqual(application.status, 'shortlisted')
        self.client.post(
            reverse('application_status', args=[application.pk]),
            {'status': 'withdrawn'},
        )
        application.refresh_from_db()
        self.assertEqual(application.status, 'withdrawn')
        self.assertEqual(application.events.count(), 2)

    def test_profile_privacy_and_applicant_consent(self):
        self.profile.discoverable = False
        self.profile.save()
        self.client.force_login(self.recruiter)
        url = reverse('candidate_detail', args=[self.candidate.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        application = Application.objects.create(candidate=self.candidate, job=self.job)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertIn(self.profile, eligible_profiles(self.job))
        application.status = 'withdrawn'
        application.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotIn(self.profile, eligible_profiles(self.job))

    def test_withdrawal_from_other_job_does_not_hide_valid_application(self):
        self.profile.discoverable = False
        self.profile.save()
        other_job = Job.objects.create(
            recruiter=self.other,
            title='Other',
            company='Other',
            location='Remote',
            employment_type='contract',
            description='SQL',
        )
        Application.objects.create(
            candidate=self.candidate,
            job=other_job,
            status='withdrawn',
        )
        Application.objects.create(candidate=self.candidate, job=self.job)
        self.assertIn(self.profile, eligible_profiles(self.job))

    def test_state_changes_require_post_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.candidate)
        self.assertEqual(
            client.post(reverse('apply', args=[self.job.pk])).status_code,
            403,
        )
        self.assertEqual(
            client.get(reverse('apply', args=[self.job.pk])).status_code,
            405,
        )

    def test_public_registration_cannot_create_admin(self):
        self.client.post(
            reverse('register'),
            {
                'username': 'new',
                'email': 'new@example.test',
                'role': 'candidate',
                'is_staff': True,
                'is_superuser': True,
                'password1': 'Example-new-234!',
                'password2': 'Example-new-234!',
            },
        )
        user = User.objects.get(username='new')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(CandidateProfile.objects.filter(user=user).exists())

    def test_email_uniqueness_is_case_insensitive_in_registration(self):
        form = RegisterForm(
            {
                'username': 'new',
                'email': 'CANDIDATE@EXAMPLE.TEST',
                'role': 'candidate',
                'password1': 'Example-new-234!',
                'password2': 'Example-new-234!',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_all_candidate_pages_render(self):
        self.client.force_login(self.candidate)
        for name in [
            'dashboard',
            'profile',
            'jobs',
            'applications',
            'recommendations',
            'password_change',
        ]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for name in ['job_detail', 'match_detail']:
            self.assertEqual(
                self.client.get(reverse(name, args=[self.job.pk])).status_code,
                200,
            )

    def test_all_recruiter_pages_render_and_export(self):
        self.client.force_login(self.recruiter)
        for name in ['dashboard', 'profile', 'my_jobs', 'job_create', 'applications']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('ranking', args=[self.job.pk])).status_code,
            200,
        )
        response = self.client.get(
            reverse('ranking', args=[self.job.pk]) + '?format=csv'
        )
        self.assertContains(response, 'Compatibility (%)')

    def test_html_input_is_escaped(self):
        self.profile.summary = '<script>alert(1)</script>'
        self.profile.save()
        self.client.force_login(self.candidate)
        response = self.client.get(
            reverse('candidate_detail', args=[self.candidate.pk])
        )
        self.assertContains(response, '&lt;script&gt;')

    def test_missing_taxonomy_shows_actionable_message(self):
        JobRequirement.objects.all().delete()
        Skill.objects.all().delete()
        self.client.force_login(self.candidate)
        response = self.client.get(reverse('recommendations'))
        self.assertContains(response, 'ESCO catalogue has not been imported')
