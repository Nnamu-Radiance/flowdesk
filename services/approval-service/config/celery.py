import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
app = Celery("approval_service")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "check-sla-deadlines": {
        "task": "apps.approvals.tasks.check_sla_deadlines",
        "schedule": 900.0,
    }
}
