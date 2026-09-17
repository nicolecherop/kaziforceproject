from pathlib import Path
import zipfile
import re
import xml.etree.ElementTree as ET
from django.urls import reverse
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
from .models import User, CandidateProfile, RecruiterProfile, Job, JobRequirement, Application


def extract_sections(text):
    """Conservative heading-based extraction; users review the resulting fields."""
    headings = {'skills': 'skills_text', 'technical skills': 'skills_text', 'education': 'qualifications',
                'qualifications': 'qualifications', 'certifications': 'certifications', 'certificates': 'certifications',
                'work experience': 'experience', 'professional experience': 'experience', 'experience': 'experience',
                'summary': 'summary', 'professional summary': 'summary'}
    sections, active = {}, None
    for line in text.splitlines():
        name, separator, remainder = line.partition(':')
        key = headings.get(name.strip().casefold())
        if key:
            active = key
            sections.setdefault(active, [])
            if separator and remainder.strip():
                sections[active].append(remainder.strip())
        elif active:
            sections[active].append(line)
    return {key: '\n'.join(lines).strip() for key, lines in sections.items()}


class CatalogueSelect(forms.Select):
    """Render selected options only; JavaScript searches the server-side catalogue."""
    def optgroups(self, name, value, attrs=None):
        original = self.choices
        if hasattr(original, 'queryset'):
            selected = [v for v in value if str(v).isdigit()]
            self.choices = [('', 'Search and select an ESCO concept')] + [(item.pk, str(item)) for item in original.queryset.filter(pk__in=selected)]
        try:
            return super().optgroups(name, value, attrs)
        finally:
            self.choices = original


class PrivateResumeValue:
    def __init__(self, value):
        self.url = reverse('resume_download', args=[value.instance.user_id])

    def __str__(self):
        return 'Download current resume'


class PrivateResumeInput(forms.ClearableFileInput):
    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if value:
            context['widget']['value'] = PrivateResumeValue(value)
        return context


class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'role', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class CandidateForm(forms.ModelForm):
    class Meta:
        model = CandidateProfile
        exclude = ['user', 'updated_at']
        widgets = {'resume': PrivateResumeInput(), **{name: forms.Textarea(attrs={'rows': 4}) for name in
                   ['summary', 'skills_text', 'qualifications', 'certifications', 'experience', 'resume_text']}}
        labels = {'skills_text': 'Your skills', 'resume_text': 'Resume text for matching'}
        help_texts = {'resume': 'PDF, DOCX or UTF-8 TXT, up to 5 MB. TXT and DOCX text is extracted. For PDF, paste the text below.',
                      'resume_text': 'Review extracted text before using it. PDF attachments need their text pasted here or entered in the profile fields.',
                      'skills_text': 'Include skills you can demonstrate. ESCO recognises preferred labels and known alternative names.'}

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
                    self.extracted_text = '\n'.join(''.join(p.itertext()) for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'))
            if len(getattr(self, 'extracted_text', '')) > 30000:
                raise ValueError('Resume text exceeds 30,000 characters')
        except (UnicodeError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
            raise ValidationError('The resume could not be read. Use a valid file with at most 30,000 text characters.') from exc
        finally:
            upload.seek(0)
        return upload

    def save(self, commit=True):
        profile = super().save(commit=False)
        if hasattr(self, 'extracted_text'):
            profile.resume_text = self.extracted_text
            for field, text in extract_sections(self.extracted_text).items():
                if not getattr(profile, field).strip():
                    setattr(profile, field, text[:profile._meta.get_field(field).max_length])
        if commit:
            profile.save()
        return profile


class RecruiterForm(forms.ModelForm):
    class Meta:
        model = RecruiterProfile
        exclude = ['user']


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        exclude = ['recruiter', 'created_at', 'updated_at']
        widgets = {'occupation': CatalogueSelect(attrs={'data-catalogue': 'occupation'}), 'deadline': forms.DateInput(attrs={'type': 'date'}),
                   **{name: forms.Textarea(attrs={'rows': 4}) for name in ['description', 'qualifications', 'certifications', 'experience']}}

    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        if deadline and deadline < timezone.localdate() and deadline != self.instance.deadline:
            raise ValidationError('Choose today or a future date.')
        return deadline


class RequirementForm(forms.ModelForm):
    class Meta:
        model = JobRequirement
        fields = ['skill', 'priority', 'essential']
        widgets = {'skill': CatalogueSelect(attrs={'data-catalogue': 'skill'})}


RequirementFormSet = inlineformset_factory(Job, JobRequirement, form=RequirementForm, extra=1, can_delete=True, max_num=30, validate_max=True)


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['cover_note']
        widgets = {'cover_note': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Briefly explain your interest in this role (optional).'})}
