"""Functional and integration tests. Taxonomy records here are synthetic fixtures."""
from datetime import timedelta
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
import zipfile
import csv
import json
from pathlib import Path
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from .forms import CandidateForm, RegisterForm, extract_sections
from .matching import MatchingEngine, Taxonomy, eligible_profiles, preprocess, clear_taxonomy_cache
from .models import User, CandidateProfile, RecruiterProfile, Job, Skill, JobRequirement, Application, ApplicationEvent, MatchResult


class BaseCase(TestCase):
    def setUp(self):
        clear_taxonomy_cache()

    def tearDown(self):
        clear_taxonomy_cache()

    @classmethod
    def setUpTestData(cls):
        cls.recruiter = User.objects.create_user('recruiter', email='recruiter@example.test', password='Example-pass-587!', role='recruiter')
        cls.other = User.objects.create_user('other', email='other@example.test', password='Example-pass-587!', role='recruiter')
        RecruiterProfile.objects.create(user=cls.recruiter, company='Test Company')
        cls.candidate = User.objects.create_user('candidate', email='candidate@example.test', password='Example-pass-587!')
        cls.profile = CandidateProfile.objects.create(user=cls.candidate, headline='Developer', skills_text='Python SQL', qualifications='Computer science', discoverable=True)
        cls.python = Skill.objects.create(uri='http://data.europa.eu/esco/skill/test-python', preferred_label='Python', alternative_labels='Py')
        cls.sql = Skill.objects.create(uri='http://data.europa.eu/esco/skill/test-sql', preferred_label='SQL', alternative_labels='Structured Query Language')
        cls.java = Skill.objects.create(uri='http://data.europa.eu/esco/skill/test-java', preferred_label='Java')
        cls.job = Job.objects.create(recruiter=cls.recruiter, title='Developer', company='Test Company', location='Nairobi', employment_type='full_time', description='Python SQL', qualifications='Computer science', status='open')
        JobRequirement.objects.create(job=cls.job, skill=cls.python, priority=5)
        JobRequirement.objects.create(job=cls.job, skill=cls.sql, priority=1)


class MatchingTests(BaseCase):
    def test_requirements_query_count_does_not_grow_with_jobs(self):
        for i in range(4):
            job = Job.objects.create(recruiter=self.recruiter, title=f'Role {i}',
                company='Test', location='Nairobi', employment_type='full_time', description='Python', status='open')
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
        self.assertEqual(taxonomy.extract('Py Structured Query Language'), taxonomy.extract('Python SQL'))

    def test_word_boundaries_prevent_java_javascript_match(self):
        _, ids = Taxonomy(Skill.objects.all()).extract('JavaScript')
        self.assertNotIn(self.java.pk, ids)

    def test_technical_punctuation_is_preserved(self):
        for name in ['C', 'C++', 'C#', 'R']:
            Skill.objects.create(uri='http://data.europa.eu/esco/skill/test-' + str(len(name)) + name.replace('#', 'sharp'), preferred_label=name)
        taxonomy = Taxonomy(Skill.objects.all())
        for name in ['C', 'C++', 'C#', 'R']:
            _, ids = taxonomy.extract(name)
            labels = {taxonomy.skills[pk].preferred_label for pk in ids}
            self.assertEqual(labels, {name})

    def test_priority_changes_ranking(self):
        self.profile.headline = self.profile.qualifications = ''
        self.profile.skills_text = 'Python'
        other_user = User.objects.create_user('sqlonly', email='sql@example.test')
        other_profile = CandidateProfile.objects.create(user=other_user, skills_text='SQL')
        self.job.title = self.job.qualifications = ''
        self.job.description = 'Python SQL'
        results = MatchingEngine().rank([self.job], [other_profile, self.profile], persist=False)
        self.assertEqual(results[0]['candidate'].pk, self.profile.pk)
        self.job.requirements.filter(skill=self.python).update(priority=1)
        self.job.requirements.filter(skill=self.sql).update(priority=5)
        results = MatchingEngine().rank([self.job], [other_profile, self.profile], persist=False)
        self.assertEqual(results[0]['candidate'].pk, other_profile.pk)

    def test_no_overlap_scores_zero_and_reports_gaps(self):
        self.profile.headline = self.profile.qualifications = ''
        self.profile.skills_text = 'pottery ceramics'
        result = MatchingEngine().rank([self.job], [self.profile])[0]
        self.assertEqual(result['score'], 0)
        self.assertEqual(len(result['missing_skills']), 2)

    def test_empty_profile_is_safe(self):
        self.profile.headline = self.profile.qualifications = self.profile.skills_text = ''
        self.assertEqual(MatchingEngine().rank([self.job], [self.profile])[0]['score'], 0)

    def test_rankings_are_capped_at_ten(self):
        for i in range(12):
            user = User.objects.create_user(f'person{i}', email=f'p{i}@example.test')
            CandidateProfile.objects.create(user=user, skills_text='Python', discoverable=True)
        self.assertEqual(len(MatchingEngine().candidates(self.job)), 10)

    def test_recommendations_exclude_closed_expired_draft(self):
        for state, deadline in [('closed', None), ('draft', None), ('open', timezone.localdate() - timedelta(days=1))]:
            Job.objects.create(recruiter=self.recruiter, title='Hidden', company='Test', location='Nairobi', employment_type='full_time', description='Python', status=state, deadline=deadline)
        results = MatchingEngine().recommendations(self.profile)
        self.assertEqual([r['job'].pk for r in results], [self.job.pk])

    def test_nltk_removes_stopwords_and_lemmatises(self):
        tokens = preprocess('the skills and databases')
        self.assertNotIn('the', tokens)
        self.assertIn('skill', tokens)
        self.assertIn('database', tokens)

    def test_names_do_not_change_scores(self):
        original = MatchingEngine().rank([self.job], [self.profile])[0]['score']
        self.candidate.first_name = 'Completely Different Name'
        self.candidate.save()
        self.assertEqual(MatchingEngine().rank([self.job], [self.profile])[0]['score'], original)


class WorkflowTests(BaseCase):
    def test_job_creation_persists_priority_and_owner(self):
        self.client.force_login(self.recruiter)
        response = self.client.post(reverse('job_create'), {'title': 'New role', 'company': 'Test Company',
            'location': 'Remote', 'employment_type': 'contract', 'description': 'Build with Python', 'status': 'open',
            'requirements-TOTAL_FORMS': '1', 'requirements-INITIAL_FORMS': '0', 'requirements-MIN_NUM_FORMS': '0',
            'requirements-MAX_NUM_FORMS': '30', 'requirements-0-skill': str(self.python.pk),
            'requirements-0-priority': '4', 'requirements-0-essential': 'on', 'recruiter': self.other.pk})
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(title='New role')
        self.assertEqual(job.recruiter, self.recruiter)
        self.assertEqual(job.requirements.get().priority, 4)

    def test_catalogue_search_requires_login_and_returns_synonyms(self):
        url = reverse('catalogue_search') + '?q=structured&kind=skill'
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.recruiter)
        self.assertEqual(self.client.get(url).json()['results'], [{'id': self.sql.pk, 'label': 'SQL'}])

    def test_candidate_cannot_create_or_edit_jobs(self):
        self.client.force_login(self.candidate)
        self.assertEqual(self.client.get(reverse('job_create')).status_code, 403)
        self.assertEqual(self.client.post(reverse('job_edit', args=[self.job.pk]), {}).status_code, 403)

    def test_recruiter_cannot_manage_another_recruiters_job(self):
        self.client.force_login(self.other)
        for name in ['job_edit', 'ranking']:
            self.assertEqual(self.client.get(reverse(name, args=[self.job.pk])).status_code, 404)

    def test_duplicate_application_is_idempotent(self):
        self.client.force_login(self.candidate)
        for _ in range(2):
            self.client.post(reverse('apply', args=[self.job.pk]), {'cover_note': 'Interested'})
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
        self.assertEqual(self.client.post(reverse('application_status', args=[application.pk]), {'status': 'shortlisted'}).status_code, 403)
        self.client.force_login(self.recruiter)
        self.client.post(reverse('application_status', args=[application.pk]), {'status': 'shortlisted'})
        application.refresh_from_db()
        self.assertEqual(application.status, 'shortlisted')
        self.assertEqual(application.events.count(), 1)
        self.client.force_login(self.candidate)
        self.client.post(reverse('application_status', args=[application.pk]), {'status': 'hired'})
        application.refresh_from_db()
        self.assertEqual(application.status, 'shortlisted')
        self.client.post(reverse('application_status', args=[application.pk]), {'status': 'withdrawn'})
        application.refresh_from_db()
        self.assertEqual(application.status, 'withdrawn')
        self.assertEqual(application.events.count(), 2)

    def test_profile_privacy_and_applicant_consent(self):
        self.profile.discoverable = False
        self.profile.save()
        self.client.force_login(self.recruiter)
        url = reverse('candidate_detail', args=[self.candidate.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        app = Application.objects.create(candidate=self.candidate, job=self.job)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertIn(self.profile, eligible_profiles(self.job))
        app.status = 'withdrawn'
        app.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotIn(self.profile, eligible_profiles(self.job))

    def test_withdrawal_from_other_job_does_not_hide_valid_application(self):
        self.profile.discoverable = False
        self.profile.save()
        other_job = Job.objects.create(recruiter=self.other, title='Other', company='Other', location='Remote', employment_type='contract', description='SQL')
        Application.objects.create(candidate=self.candidate, job=other_job, status='withdrawn')
        Application.objects.create(candidate=self.candidate, job=self.job)
        self.assertIn(self.profile, eligible_profiles(self.job))

    def test_state_changes_require_post_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.candidate)
        self.assertEqual(client.post(reverse('apply', args=[self.job.pk])).status_code, 403)
        self.assertEqual(client.get(reverse('apply', args=[self.job.pk])).status_code, 405)

    def test_public_registration_cannot_create_admin(self):
        self.client.post(reverse('register'), {'username': 'new', 'email': 'new@example.test', 'role': 'candidate', 'is_staff': True,
            'is_superuser': True, 'password1': 'Example-new-234!', 'password2': 'Example-new-234!'})
        user = User.objects.get(username='new')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(CandidateProfile.objects.filter(user=user).exists())

    def test_email_uniqueness_is_case_insensitive_in_registration(self):
        form = RegisterForm({'username': 'new', 'email': 'CANDIDATE@EXAMPLE.TEST', 'role': 'candidate', 'password1': 'Example-new-234!', 'password2': 'Example-new-234!'})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_all_candidate_pages_render(self):
        self.client.force_login(self.candidate)
        for name in ['dashboard', 'profile', 'jobs', 'applications', 'recommendations', 'password_change']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for name in ['job_detail', 'match_detail']:
            self.assertEqual(self.client.get(reverse(name, args=[self.job.pk])).status_code, 200)

    def test_all_recruiter_pages_render_and_export(self):
        self.client.force_login(self.recruiter)
        for name in ['dashboard', 'profile', 'my_jobs', 'job_create', 'applications']:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse('ranking', args=[self.job.pk])).status_code, 200)
        response = self.client.get(reverse('ranking', args=[self.job.pk]) + '?format=csv')
        self.assertContains(response, 'Compatibility (%)')

    def test_html_input_is_escaped(self):
        self.profile.summary = '<script>alert(1)</script>'
        self.profile.save()
        self.client.force_login(self.candidate)
        response = self.client.get(reverse('candidate_detail', args=[self.candidate.pk]))
        self.assertContains(response, '&lt;script&gt;')

    def test_missing_taxonomy_shows_actionable_message(self):
        JobRequirement.objects.all().delete()
        Skill.objects.all().delete()
        self.client.force_login(self.candidate)
        self.assertContains(self.client.get(reverse('recommendations')), 'ESCO catalogue has not been imported')


class ResumeTests(BaseCase):
    def test_current_resume_link_uses_private_download_view(self):
        self.profile.resume.name = 'resumes/test/private.pdf'
        form = CandidateForm(instance=self.profile)
        markup = str(form['resume'])
        self.assertIn(reverse('resume_download', args=[self.candidate.pk]), markup)
        self.assertNotIn('resumes/test/private.pdf', markup)

    def test_resume_sections_are_extracted(self):
        sections = extract_sections('Skills: Python, SQL\nEducation\nBSc Computer Science\nCertifications\nSoftware testing\nWork experience\nBuilt a portal')
        self.assertEqual(sections['skills_text'], 'Python, SQL')
        self.assertEqual(sections['qualifications'], 'BSc Computer Science')
        self.assertEqual(sections['experience'], 'Built a portal')

    def test_txt_resume_text_is_extracted(self):
        upload = SimpleUploadedFile('resume.txt', b'Python SQL developer', content_type='text/plain')
        form = CandidateForm({'skills_text': 'Python'}, {'resume': upload}, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            profile = form.save()
            self.assertEqual(profile.resume_text, 'Python SQL developer')

    def test_docx_resume_text_is_extracted(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Python developer</w:t></w:r></w:p></w:body></w:document>')
        form = CandidateForm({}, {'resume': SimpleUploadedFile('cv.docx', buffer.getvalue())}, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.extracted_text, 'Python developer')

    def test_executable_upload_rejected(self):
        form = CandidateForm({}, {'resume': SimpleUploadedFile('malware.exe', b'payload')}, instance=self.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('resume', form.errors)

    def test_fake_pdf_rejected(self):
        form = CandidateForm({}, {'resume': SimpleUploadedFile('cv.pdf', b'not a pdf')}, instance=self.profile)
        self.assertFalse(form.is_valid())

    def test_oversized_file_rejected(self):
        form = CandidateForm({}, {'resume': SimpleUploadedFile('cv.txt', b'x' * (5 * 1024 * 1024 + 1))}, instance=self.profile)
        self.assertFalse(form.is_valid())

    def test_private_resume_not_available_to_other_candidates(self):
        other = User.objects.create_user('stranger', email='stranger@example.test')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('resume_download', args=[self.candidate.pk])).status_code, 403)


class ManagementCommandTests(BaseCase):
    def test_esco_import_updates_existing_uri_without_breaking_requirements(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'skills.csv'
            with path.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=['conceptUri', 'preferredLabel', 'altLabels'])
                writer.writeheader()
                writer.writerow({'conceptUri': self.python.uri, 'preferredLabel': 'Python language', 'altLabels': 'Python\nPy'})
            call_command('import_esco', str(path), esco_version='1.2.0', stdout=StringIO())
        self.python.refresh_from_db()
        self.assertEqual(self.python.preferred_label, 'Python language')
        self.assertEqual(self.job.requirements.get(skill=self.python).priority, 5)

    def test_evaluation_outputs_metrics_for_supplied_fixture_labels(self):
        with TemporaryDirectory() as directory:
            labels = Path(directory) / 'labels.csv'
            output = Path(directory) / 'report.json'
            with labels.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                writer.writerow(['job_id', 'candidate_id', 'relevance', 'missing_skill_uris'])
                writer.writerow([self.job.pk, self.candidate.pk, 3, '[]'])
            call_command('evaluate_matching', str(labels), output=output, stdout=StringIO())
            report = json.loads(output.read_text())
            self.assertEqual(report['pairs'], 1)
            self.assertEqual(report['mean_ndcg_at_10'], 1)
            self.assertEqual(report['threshold_accuracy'], 1)
            self.assertEqual(report['skill_gap_micro_f1'], 1)
