from django.urls import path
from . import views

urlpatterns = [
    # Landing page
    path('', views.index, name='index'),
    
    # Dashboard and profile
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),

    # Backup user investigations view
    path('investigations/', views.get_user_investigations, name='investigations_list'),
    path('investigations/<str:accession_code>/', views.investigation_detail, name='investigation_detail'),
    path('investigations/<str:accession_code>/edit/', views.investigation_edit, name='investigation_edit'),
    path('investigations/create/', views.create_investigation, name='create_investigation'),

]