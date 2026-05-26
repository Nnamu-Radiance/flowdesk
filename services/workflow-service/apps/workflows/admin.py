from django.contrib import admin

from apps.workflows.models import CSVImportJob, Document, Workflow

admin.site.register(Workflow)
admin.site.register(Document)
admin.site.register(CSVImportJob)
