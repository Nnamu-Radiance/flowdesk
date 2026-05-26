from django.contrib import admin

from apps.workflows.models import Document, Workflow

admin.site.register(Document)
admin.site.register(Workflow)
