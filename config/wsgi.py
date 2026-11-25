"""
WSGI config for config project.

Vercel, ``app`` adlı değişkeni arar; ``application`` ile aynı nesnedir.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
app = application
