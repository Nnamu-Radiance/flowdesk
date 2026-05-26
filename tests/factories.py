import factory
from django.utils import timezone

from apps.approvals.models import ApprovalType
from apps.auth.models import CustomUser
from apps.workflows.models import Workflow


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CustomUser

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    role_type = CustomUser.ROLE_SUBMITTER


class ApprovalTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApprovalType

    name = factory.Sequence(lambda n: f"Type {n}")
    sla_hours = 48


class WorkflowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Workflow

    name = factory.Sequence(lambda n: f"Workflow {n}")
    created_by = factory.SubFactory(UserFactory)
    approval_type = factory.SubFactory(ApprovalTypeFactory)
    deadline = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(days=1))
