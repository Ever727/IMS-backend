#!/bin/sh
service redis-server start

python3 manage.py makemigrations account friendship chat
python3 manage.py migrate


daphne -b 0.0.0.0 -p 80 tasright_backend.asgi:application 