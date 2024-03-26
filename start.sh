#!/bin/sh
python3 manage.py makemigrations account friendship
python3 manage.py migrate

# Run with uWSGI
uwsgi --module=tasright_backend.wsgi:application \
    --env DJANGO_SETTINGS_MODULE=tasright_backend.settings \
    --master \
    --http=0.0.0.0:80 \
    --processes=5 \
    --harakiri=20 \
    --max-requests=5000 \
    --vacuum