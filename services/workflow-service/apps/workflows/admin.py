from django.contrib import admin

from apps.workflows.models import (
    ApprovalStop,
    CSVImportJob,
    Document,
    Workflow,
    WorkflowDocumentRequirement,
    WorkflowDocumentUpload,
)

admin.site.register(Workflow)
admin.site.register(Document)
admin.site.register(CSVImportJob)
admin.site.register(ApprovalStop)
admin.site.register(WorkflowDocumentRequirement)
admin.site.register(WorkflowDocumentUpload)
