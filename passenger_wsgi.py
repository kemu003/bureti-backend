import sys
import os
import django

# Add your project directory to the sys.path
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django
django.setup()

# Import the WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()