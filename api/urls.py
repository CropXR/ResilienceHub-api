from django.urls import path, include
from django.shortcuts import render, redirect

urlpatterns = [
    path('v1/', include('api.v1.urls')),
    path('v2/', include('api.v2.urls')),
    #path('', include('isa_api.v1.urls')),
]