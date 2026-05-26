from .base import *

DEBUG = False
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "test.sqlite3"}}
CELERY_TASK_ALWAYS_EAGER = True
