from django.urls import path
from . import views

urlpatterns = [
    path('messages', views.messages),
    # path('conversations', views.conversations),
    # path('conversations/<int:conversation_id>/join', views.join_conversation),
    # path('conversations/<int:conversation_id>/leave', views.leave_conversation),
]
