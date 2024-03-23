from django.urls import path
from . import views


urlpatterns = [
    path('register/', views.register, name='register'),
    path('delete/', views.delete, name='delete'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('', views.login, name='login'),
]