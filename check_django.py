import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()
from django.conf import settings
print('LOGIN_URL:', settings.LOGIN_URL)
print('LOGOUT_REDIRECT_URL:', settings.LOGOUT_REDIRECT_URL)