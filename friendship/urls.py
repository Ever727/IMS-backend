from django.urls import path
from . import views


urlpatterns = [
    path('add_friend/', views.add_friend, name='add'),
    path('delete_friend/', views.delete_friend, name='delete_friend'),
    path('accept_friend/', views.accept_friend, name='accept_friend'),
    path('myfriends/<userId>/', views.get_friend_list, name='friendlist'),
    path('myrequests/<userId>/', views.get_friendshipRequest_list, name='friendlist'),
    path('check_friendship/', views.check_friendship, name='check_friendship'),
    path('add_tag/', views.add_tag, name='add_tag')
]