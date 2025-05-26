# forms.py
from django import forms
from .database_models.models import Investigation, Study


class InvestigationForm(forms.ModelForm):
    """Simple form for creating Investigation objects."""
    
    class Meta:
        model = Investigation
        fields = ['title', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'})
        }

class StudyForm(forms.ModelForm):
    """Simple form for creating Study objects in the context of an Investigation."""
    
    class Meta:
        model = Study
        fields = ['title', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'})
        }   