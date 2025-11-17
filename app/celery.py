import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
app = Celery('app')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule (periodic tasks)
app.conf.beat_schedule = {
    'sync-vsphere-inventory-every-hour': {
        'task': 'app.tasks.sync_vsphere_inventory',
        'schedule': crontab(minute=0, hour='*/1'),  # Every hour
    },
}