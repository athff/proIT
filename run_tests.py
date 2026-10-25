import os
import sys

# Set up Django environment
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

# Import and setup Django
from importlib import reload
import importlib

# Add the project to path
sys.path.insert(0, 'E:\\proIT')

# Setup Django
import django
django.setup()

# Now run the tests
from django.core.management import call_command

# Verbosity 2 for detailed output
call_command('test', 'config.tests', verbosity=2, keepdb=False, interactive=False)