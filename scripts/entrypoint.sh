#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "--- Running Migrations ---"
python manage.py migrate --noinput

echo "--- Bootstrapping Admin ---"
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell <<'PYTHON'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ['DJANGO_SUPERUSER_USERNAME']
password = os.environ['DJANGO_SUPERUSER_PASSWORD']
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, '', password)
    print(f'Admin user "{username}" created successfully')
else:
    print(f'Admin user "{username}" already exists')
PYTHON
fi

# Run the command passed to the script (e.g., 'python manage.py runserver' or 'gunicorn')
exec "$@"