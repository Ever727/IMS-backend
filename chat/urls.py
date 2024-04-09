from django.urls import path
from . import views

urlpatterns = [
    path('messages/', views.messages),
    path('conversations/', views.conversations),
    path('delete_message/', views.delete_message),
    path('read_message/', views.read_message),
]
