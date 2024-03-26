from django.urls import path
from . import views


urlpatterns = [
    path('register/', views.register, name='register'),
    path('delete/', views.delete, name='delete'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('search/<str:userId>/', views.search_user, name='search'),
    path('', views.login, name='login'),
]