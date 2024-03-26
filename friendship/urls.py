from django.urls import path
from . import views


urlpatterns = [
    path('search/<userId>/',views.search_user, name='search'),
    path('add_friend/', views.add_friend, name='add'),
    path('delete_friend/', views.delete_friend, name='delete_friend'),
]