from django.urls import path, include
from rest_framework.routers import DefaultRouter

from api.v3 import views
from api.v3.views import InvestigationViewSet

router = DefaultRouter()
router.register(r'investigations', InvestigationViewSet, basename='investigation')

urlpatterns = [
    path('', include(router.urls)),
    path('catalogue/', views.catalogue_html, name='catalogue'),
    path('', views.index_html, name='index'),
]