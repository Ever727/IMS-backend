#!/bin/sh
python3 manage.py makemigrations account friendship chat
python3 manage.py migrate

# Run with uWSGI
# uvicorn tasright_backend.asgi:application \
#     --host 0.0.0.0 \
#     --port 80 \
#     --workers 5 \
#     --limit-concurrency 5000 \
#     --timeout-keep-alive 20 \
#     --reload

daphne -b 0.0.0.0 -p 80 tasright_backend.asgi:application 