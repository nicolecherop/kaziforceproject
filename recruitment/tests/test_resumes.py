from io import BytesIO
from tempfile import TemporaryDirectory
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from ..forms import CandidateForm, extract_sections
from ..models import User
from .base import BaseCase


class ResumeTests(BaseCase):
    def test_current_resume_link_uses_private_download_view(self):
        self.profile.resume.name = 'resumes/test/private.pdf'
        form = CandidateForm(instance=self.profile)
        markup = str(form['resume'])
        self.assertIn(reverse('resume_download', args=[self.candidate.pk]), markup)
        self.assertNotIn('resumes/test/private.pdf', markup)

    def test_resume_sections_are_extracted(self):
        sections = extract_sections(
            'Skills: Python, SQL\nEducation\nBSc Computer Science\n'
            'Certifications\nSoftware testing\nWork experience\nBuilt a portal'
        )
        self.assertEqual(sections['skills_text'], 'Python, SQL')
        self.assertEqual(sections['qualifications'], 'BSc Computer Science')
        self.assertEqual(sections['experience'], 'Built a portal')

    def test_txt_resume_text_is_extracted(self):
        upload = SimpleUploadedFile(
            'resume.txt', b'Python SQL developer', content_type='text/plain'
        )
        form = CandidateForm(
            {'skills_text': 'Python'},
            {'resume': upload},
            instance=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            profile = form.save()
            self.assertEqual(profile.resume_text, 'Python SQL developer')

    def test_docx_resume_text_is_extracted(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr(
                'word/document.xml',
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>Python developer</w:t></w:r></w:p>'
                '</w:body></w:document>',
            )
        upload = SimpleUploadedFile('cv.docx', buffer.getvalue())
        form = CandidateForm({}, {'resume': upload}, instance=self.profile)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.extracted_text, 'Python developer')

    def test_executable_upload_rejected(self):
        upload = SimpleUploadedFile('malware.exe', b'payload')
        form = CandidateForm({}, {'resume': upload}, instance=self.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('resume', form.errors)

    def test_fake_pdf_rejected(self):
        upload = SimpleUploadedFile('cv.pdf', b'not a pdf')
        form = CandidateForm({}, {'resume': upload}, instance=self.profile)
        self.assertFalse(form.is_valid())

    def test_oversized_file_rejected(self):
        upload = SimpleUploadedFile(
            'cv.txt', b'x' * (5 * 1024 * 1024 + 1)
        )
        form = CandidateForm({}, {'resume': upload}, instance=self.profile)
        self.assertFalse(form.is_valid())

    def test_private_resume_not_available_to_other_candidates(self):
        other = User.objects.create_user('stranger', email='stranger@example.test')
        self.client.force_login(other)
        response = self.client.get(
            reverse('resume_download', args=[self.candidate.pk])
        )
        self.assertEqual(response.status_code, 403)
