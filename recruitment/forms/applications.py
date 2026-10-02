from django import forms

from ..models import Application


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['cover_note']
        widgets = {
            'cover_note': forms.Textarea(
                attrs={
                    'rows': 4,
                    'placeholder': 'Briefly explain your interest in this role (optional).',
                }
            )
        }
