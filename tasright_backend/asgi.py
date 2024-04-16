"""
ASGI config for tasright_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path, path
from .consumer import ChatConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tasright_backend.settings')
django.setup()


application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter([
           path('chat/ws/', ChatConsumer.as_asgi()),
        ])
    ),
    'websocket-secure': AuthMiddlewareStack(
        URLRouter([
            path('chat/ws/', ChatConsumer.as_asgi()),
        ])
    ),
})
