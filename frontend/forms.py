from django import forms
from api.models import Investigation

class InvestigationForm(forms.ModelForm):
    class Meta:
        model = Investigation
        fields = [
            'title', 
            'description', 
            'start_date', 
            'end_date', 
            'submission_date', 
            'public_release_date', 
            'security_level'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'submission_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'public_release_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'security_level': forms.Select(attrs={'class': 'form-control'}),
        }