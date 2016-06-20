import os
import sys

sys.path.append('/home/xiakong/amazon_web')
os.environ['DJANGO_SETTINGS_MODULE'] = 'amazon_web.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
