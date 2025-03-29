from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .views import InvestigationViewSet, StudyViewSet, AssayViewSet, SampleViewSet, ISAExportView

# Main router for flat routes
router = DefaultRouter()
router.register(r'investigations', InvestigationViewSet, basename='investigation')
router.register(r'studies', StudyViewSet, basename='study')
#router.register(r'assays', AssayViewSet, basename='assay')
#router.register(r'samples', SampleViewSet, basename='sample')


urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Authentication token endpoint
    path('token/', obtain_auth_token, name='api_token'),

    # Direct access URLs by accession code
    re_path(r'^(?P<accession_code>CXRP\d+)/?$', 
            InvestigationViewSet.as_view({'get': 'retrieve'}), 
            name='direct-investigation-access'),
    re_path(r'^(?P<accession_code>CXRS\d+)/?$', 
            StudyViewSet.as_view({'get': 'retrieve'}), 
            name='direct-study-access'),
    #re_path(r'^(?P<accession_code>CXRA\d+)/?$', 
    #        AssayViewSet.as_view({'get': 'retrieve'}), 
    #        name='direct-assay-access'),
    #re_path(r'^(?P<accession_code>CXRX\d+)/?$', 
    #        SampleViewSet.as_view({'get': 'retrieve'}), 
    #        name='direct-assay-access'),
    # ISA Export endpoint - using re_path instead of path for more flexibility
    #path('export/isa/<str:code>', ISAExportView.as_view(), name='isa-export'),

]