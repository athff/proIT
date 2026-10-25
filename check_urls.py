import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

from django.urls import reverse
from django.conf import settings

print('LOGIN_URL:', settings.LOGIN_URL)
print('LOGOUT_REDIRECT_URL:', settings.LOGOUT_REDIRECT_URL)
print('LOGIN_REDIRECT_URL:', settings.LOGIN_REDIRECT_URL)
print()
print('reverse("login"):', reverse('login'))
print('reverse("logout"):', reverse('logout'))
print('reverse("dashboard"):', reverse('dashboard'))