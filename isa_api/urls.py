from django.urls import path, include
from django.shortcuts import render, redirect

urlpatterns = [
    path('v1/', include('isa_api.v1.urls')),
    path('v2/', include('isa_api.v2.urls')),
    #path('', include('isa_api.v1.urls')),
]