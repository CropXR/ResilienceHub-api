# urls.py
from django.urls import path, include, re_path
from rest_framework_nested import routers
from rest_framework.authtoken.views import obtain_auth_token

from .views import InvestigationViewSet, StudyViewSet

# Main router
router = routers.DefaultRouter()
router.register(r'investigations', InvestigationViewSet)

# Nested router for studies under investigations
studies_router = routers.NestedSimpleRouter(
    router,
    r'investigations',
    lookup='investigation'
)

studies_router.register(
    r'studies',
    StudyViewSet,
    basename='investigation-studies'
)

urlpatterns = [
    # Include all nested routers
    path('', include(router.urls)),
    path('', include(studies_router.urls)),
    path('token/', obtain_auth_token, name='api_token'),

    # Direct access URLs - no nesting required
    re_path(r'^(?P<accession_code>CXRP\d+)/?$', 
            InvestigationViewSet.as_view({'get': 'retrieve'}), 
            name='direct-investigation-access'),
    re_path(r'^(?P<accession_code>CXRS\d+)/?$', 
            StudyViewSet.as_view({'get': 'retrieve'}), 
            name='direct-study-access'),
]