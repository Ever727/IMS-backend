from django.urls import path
from . import views

urlpatterns = [
    path('messages/', views.messages),
    path('conversations/', views.conversations),
    path('delete_message/', views.delete_message),
    path('read_message/', views.read_message),
    path('get_conversation_ids/', views.get_conversation_ids),
    path('get_unread_count/', views.get_unread_count),
    path('upload_notification/', views.upload_notification),
    path('set_host/', views.set_host),
    path('set_admin/', views.set_admin),
    path('remove_admin/', views.remove_admin),
    path('kick_member/', views.kick_member),
    path('exit_group/', views.exit_group),
    path('invite_member/', views.invite_member),
    path('group_requests/<str:userId>/', views.group_requests),
    path('accept_group_invitation/', views.accept_invitation),
    path('update_group/', views.update_group),
]
