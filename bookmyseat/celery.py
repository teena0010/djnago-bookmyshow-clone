import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyseat.settings')

app = Celery('bookmyseat')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.broker_transport_options = {
    'ssl': {
        'cert_reqs': 'CERT_REQUIRED',
    },
    'socket_connect_timeout': 30,
}
