from django.apps import AppConfig


class WorkflowsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.workflows"

    def ready(self):
        from apps.workflows import signals  # noqa: F401
