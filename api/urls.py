from django.urls import path, include
from django.shortcuts import render, redirect

urlpatterns = [
    path('v3/', include('api.v3.urls')),
    #path('v2/', include('api.v2.urls')),
    #path('', include('isa_api.v1.urls')),
]