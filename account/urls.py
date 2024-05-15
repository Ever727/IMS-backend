from django.urls import path
from . import views


urlpatterns = [
    path('register/', views.register, name='register'),
    path('delete/', views.delete, name='delete'),
    path('login/', views.login, name='login'),
    path('search/<str:userId>/', views.search_user, name='search'),
    path('', views.login, name='login'),
    path('profile/<str:userId>/', views.profile, name='profile'),
    path('update_profile/<str:userId>/', views.update_profile, name='updata_profile')
]