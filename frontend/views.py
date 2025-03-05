from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import requests
from django.conf import settings
from isa_api.models import Investigation, InvestigationPermission
from .forms import InvestigationForm
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone

from django.contrib.auth.decorators import login_required, permission_required

def index(request):
    """Landing page view"""
    return render(request, 'frontend/landing.html')

@login_required
def dashboard(request):
    """Dashboard view showing user's investigations and studies"""
    context = {
        'user': request.user,
    }
    return render(request, 'frontend/pages/dashboard.html', context)

@login_required
def profile(request):
    """User profile page"""
    context = {
        'user': request.user,
    }
    return render(request, 'frontend/accounts/profile.html', context)

@login_required
def get_user_investigations(request):
    """
    A simple view to get investigations where the user has specific permissions
    This is a backup if the API isn't working
    """
    user = request.user
    error_message = None
    investigations_data = []
    
    try:
        # Query by the user_permissions relationship
        # Only include investigations where user is reader, contributor, or owner
        investigations = Investigation.objects.filter(
            user_permissions__user=user,
            user_permissions__role__in=['contributor', 'owner']
        ).distinct().order_by('-created_at')
        
        # Format data for response
        for inv in investigations:
            # Get the user's role for this investigation
            try:
                permission = inv.user_permissions.get(
                    user=user, 
                    role__in=['contributor', 'owner']
                )
                role = permission.get_role_display()
            except:
                role = "Unknown"
                
            investigations_data.append({
                'id': inv.id,
                'accession_code': inv.accession_code,
                'title': inv.title,
                'description': inv.description,
                'security_level': inv.security_level,
                'created_at': inv.created_at.isoformat() if inv.created_at else None,
                'role': role,
                'studies_count': inv.studies.count(),
            })
    except Exception as e:
        error_message = f"Error fetching investigations: {str(e)}"
    
    if request.GET.get('format') == 'json':
        return JsonResponse({
            'investigations': investigations_data,
            'error': error_message
        })
    
    context = {
        'investigations': investigations_data,
        'user': user,
        'error': error_message,
        'auth_token': False,
        'pagination': {
            'count': len(investigations_data),
            'next': None,
            'previous': None,
            'current_page': 1,
        },
    }
    return render(request, 'frontend/pages/investigations_list.html', context)


@login_required
def investigation_detail(request, accession_code):
    """
    View to display details of a specific investigation
    """
    try:
        # Attempt to fetch the investigation
        investigation = Investigation.objects.get(accession_code=accession_code)
        
        # Check user permissions
        user_permission = investigation.user_permissions.filter(
            user=request.user, 
            role__in=['reader', 'contributor', 'owner']
        ).first()
        
        if not user_permission:
            messages.error(request, "You do not have permission to view this investigation.")
            return redirect('investigations_list')
        
        # Prepare context with investigation details
        context = {
            'investigation': investigation,
            'user_role': user_permission.role,
            'studies': investigation.studies.all() if hasattr(investigation, 'studies') else [],
        }
        
        return render(request, 'frontend/pages/investigation_detail.html', context)
    
    except Investigation.DoesNotExist:
        messages.error(request, "Investigation not found.")
        return redirect('investigations_list')
    
@login_required
def investigation_edit(request, accession_code):
    """
    View to edit an existing investigation
    """
    try:
        # Fetch the investigation
        investigation = Investigation.objects.get(accession_code=accession_code)
        
        # Use can_write method to check permissions
        if not investigation.can_write(request.user):
            messages.error(request, "You do not have permission to edit this investigation.")
            return redirect('investigations_list')
        
        if request.method == 'POST':
            form = InvestigationForm(request.POST, instance=investigation)
            if form.is_valid():
                try:
                    investigation = form.save()
                    messages.success(request, 'Investigation updated successfully.')
                    return redirect('investigation_detail', accession_code=investigation.accession_code)
                except Exception as e:
                    messages.error(request, f'Error updating investigation: {str(e)}')
        else:
            form = InvestigationForm(instance=investigation)
        
        context = {
            'form': form,
            'investigation': investigation,
            'title': f'Edit Investigation: {investigation.title}',
        }
        return render(request, 'frontend/pages/edit_investigation.html', context)
    
    except Investigation.DoesNotExist:
        messages.error(request, "Investigation not found.")
        return redirect('investigations_list')
    
@login_required
@permission_required('isa_api.add_investigation', raise_exception=True)
def create_investigation(request):
    """
    View to create a new investigation
    """
    if request.method == 'POST':
        form = InvestigationForm(request.POST)
        if form.is_valid():
            try:
                # Create the investigation
                investigation = form.save(commit=False)
                
                # Set the current user as the owner
                investigation.save()
                
                # Assign the current user as the owner of the investigation
                investigation.assign_role(request.user, 'owner')
                
                messages.success(request, 'Investigation created successfully.')
                return redirect('investigation_detail', accession_code=investigation.accession_code)
            except Exception as e:
                messages.error(request, f'Error creating investigation: {str(e)}')
    else:
        # Initialize the form with default security level
        form = InvestigationForm(initial={
            'security_level': 'confidential',  # or your preferred default
            'submission_date': timezone.now().date(),
        })
    
    context = {
        'form': form,
        'title': 'Create New Investigation',
    }
    return render(request, 'frontend/pages/create_investigation.html', context)

