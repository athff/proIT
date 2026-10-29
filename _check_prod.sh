#!/usr/bin/env bash
base="DJANGO_ENV=production DEBUG=False SECRET_KEY=a_long_random_secret_key_for_testing_0123456789 ALLOWED_HOSTS=example.com"
probe="import os,django
os.environ['DJANGO_SETTINGS_MODULE']='config.settings'
try:
    django.setup(); print('  -> STARTED (no error raised)')
except Exception as e: print('  -> '+type(e).__name__+': '+str(e)[:170])"

for case in "PROIT_EMAIL_BACKEND=diagnostic_smtp" "PROIT_EMAIL_BACKEND=resend" "PROIT_EMAIL_BACKEND=console"; do
  echo "--- incomplete: $case ---"
  env $base $case /tmp/proitvenv/bin/python -c "$probe" 2>&1 | tail -1
done

echo "--- complete: resend ---"
env $base PROIT_EMAIL_BACKEND=resend RESEND_API_KEY=re_live DEFAULT_FROM_EMAIL=a@b.com \
  /tmp/proitvenv/bin/python -c "$probe" 2>&1 | tail -1

echo "--- complete: smtp ---"
env $base PROIT_EMAIL_BACKEND=smtp EMAIL_HOST=smtp.gmail.com EMAIL_HOST_USER=a@b.com \
  EMAIL_HOST_PASSWORD=pw EMAIL_USE_TLS=True DEFAULT_FROM_EMAIL=a@b.com \
  /tmp/proitvenv/bin/python -c "$probe" 2>&1 | tail -1
