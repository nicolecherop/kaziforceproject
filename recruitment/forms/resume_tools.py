from django import forms
from django.urls import reverse


def extract_sections(text):
    """Extract common resume sections by their headings."""
    headings = {
        'skills': 'skills_text',
        'technical skills': 'skills_text',
        'education': 'qualifications',
        'qualifications': 'qualifications',
        'certifications': 'certifications',
        'certificates': 'certifications',
        'work experience': 'experience',
        'professional experience': 'experience',
        'experience': 'experience',
        'summary': 'summary',
        'professional summary': 'summary',
    }
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
    """Render selected options only; JavaScript searches the catalogue."""

    def optgroups(self, name, value, attrs=None):
        original = self.choices
        if hasattr(original, 'queryset'):
            selected = [item for item in value if str(item).isdigit()]
            self.choices = [('', 'Search and select an ESCO concept')] + [
                (item.pk, str(item)) for item in original.queryset.filter(pk__in=selected)
            ]
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
