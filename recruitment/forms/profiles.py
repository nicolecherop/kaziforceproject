from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from django import forms
from django.core.exceptions import ValidationError

from ..models import CandidateProfile, RecruiterProfile
from .resume_tools import PrivateResumeInput, extract_sections


class CandidateForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        exclude = ['user', 'updated_at']
        widgets = {
            'resume': PrivateResumeInput(),
            **{
                name: forms.Textarea(attrs={'rows': 4})
                for name in [
                    'summary',
                    'skills_text',
                    'qualifications',
                    'certifications',
                    'experience',
                    'resume_text',
                ]
            },
        }
        labels = {'skills_text': 'Your skills', 'resume_text': 'Resume text for matching'}
        help_texts = {
            'resume': 'PDF, DOCX or UTF-8 TXT, up to 5 MB. TXT and DOCX text is extracted. For PDF, paste the text below.',
            'resume_text': 'Review extracted text before using it. PDF attachments need their text pasted here or entered in the profile fields.',
            'skills_text': 'Include skills you can demonstrate. ESCO recognises preferred labels and known alternative names.',
        }

    def clean_resume(self):
        upload = self.cleaned_data.get('resume')
        if not upload or not hasattr(upload, 'content_type'):
            return upload
        if upload.size > 5 * 1024 * 1024:
            raise ValidationError('Resume must be 5 MB or smaller.')
        suffix = Path(upload.name).suffix.lower()
        if suffix not in ('.pdf', '.docx', '.txt'):
            raise ValidationError('Choose a PDF, DOCX or TXT resume.')
        try:
            if suffix == '.txt':
                self.extracted_text = upload.read().decode('utf-8-sig')
            elif suffix == '.pdf':
                if upload.read(5) != b'%PDF-':
                    raise ValueError('Invalid PDF signature')
            else:
                with zipfile.ZipFile(upload) as archive:
                    info = archive.getinfo('word/document.xml')
                    if info.file_size > 2 * 1024 * 1024:
                        raise ValueError('Document text too large')
                    data = archive.read(info)
                    if b'<!DOCTYPE' in data or b'<!ENTITY' in data:
                        raise ValueError('Unsupported document structure')
                    root = ET.fromstring(data)
                    self.extracted_text = '\n'.join(
                        ''.join(paragraph.itertext())
                        for paragraph in root.iter(
                            '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'
                        )
                    )
            if len(getattr(self, 'extracted_text', '')) > 30000:
                raise ValueError('Resume text exceeds 30,000 characters')
        except (UnicodeError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
            raise ValidationError(
                'The resume could not be read. Use a valid file with at most 30,000 text characters.'
            ) from exc
        finally:
            upload.seek(0)
        return upload

    def save(self, commit=True):
        profile = super().save(commit=False)
        if hasattr(self, 'extracted_text'):
            profile.resume_text = self.extracted_text
            for field, text in extract_sections(self.extracted_text).items():
                if not getattr(profile, field).strip():
                    field_limit = profile._meta.get_field(field).max_length
                    setattr(profile, field, text[:field_limit])
        if commit:
            profile.save()
        return profile


class RecruiterForm(forms.ModelForm):
    class Meta:
        model = RecruiterProfile
        exclude = ['user']
