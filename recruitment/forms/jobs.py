from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone

from ..models import Job, JobRequirement
from .resume_tools import CatalogueSelect


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        exclude = ['recruiter', 'created_at', 'updated_at']
        widgets = {
            'occupation': CatalogueSelect(attrs={'data-catalogue': 'occupation'}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            **{
                name: forms.Textarea(attrs={'rows': 4})
                for name in ['description', 'qualifications', 'certifications', 'experience']
            },
        }

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


RequirementFormSet = inlineformset_factory(
    Job,
    JobRequirement,
    form=RequirementForm,
    extra=1,
    can_delete=True,
    max_num=30,
    validate_max=True,
)
