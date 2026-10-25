import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

from django.urls import reverse, get_resolver
from django.conf import settings

print('LOGIN_URL:', settings.LOGIN_URL)
print('LOGOUT_REDIRECT_URL:', settings.LOGOUT_REDIRECT_URL)
print('LOGIN_REDIRECT_URL:', settings.LOGIN_REDIRECT_URL)
print()
print('reverse("login"):', reverse('login'))
print('reverse("logout"):', reverse('logout'))
print('reverse("dashboard"):', reverse('dashboard'))
print()

# Check all URL names
print('All URL names:')
for pattern in get_resolver().url_patterns:
    try:
        if hasattr(pattern, 'name') and pattern.name:
            try:
                r = reverse(pattern.name)
                print(f'  {pattern.name}: {r}')
            except:
                print(f'  {pattern.name}: (reverse failed)')
    except:
        pass