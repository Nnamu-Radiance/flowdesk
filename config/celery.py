import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("flowdesk")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "escalate-sla-deadlines": {
        "task": "apps.workflows.tasks.escalate_sla_deadlines",
        "schedule": 300.0,
    },
}
