from django.contrib import admin

from apps.approvals.models import (
    ApprovalChain,
    ApprovalRecord,
    ApprovalStep,
    ApprovalType,
)

admin.site.register(ApprovalType)
admin.site.register(ApprovalChain)
admin.site.register(ApprovalStep)
admin.site.register(ApprovalRecord)
