#!/usr/bin/env bash
set -eu

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py collectstatic --no-input
