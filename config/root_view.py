# In custom_views.py or a new file like root_views.py
from django.shortcuts import render, redirect

def root_view(request):
    """A simple root view that redirects to the API interface or shows a landing page"""
    # Option 1: Redirect to API interface
    return redirect('/admin')
