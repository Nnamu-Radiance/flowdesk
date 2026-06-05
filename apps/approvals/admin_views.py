from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import response, viewsets
from rest_framework.decorators import action
from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication

from apps.approvals.models import ApprovalChain, ApprovalStep, ApprovalType
from apps.approvals.serializers import (
    ApprovalChainSerializer,
    ApprovalStepWriteSerializer,
    ApprovalTypeSerializer,
)
from apps.auth.permissions import IsAdminUser
from apps.auth.serializers import UserSerializer

User = get_user_model()


class ApprovalTypeAdminViewSet(viewsets.ModelViewSet):
    queryset = ApprovalType.objects.order_by("name")
    serializer_class = ApprovalTypeSerializer
    authentication_classes = [JWTStatelessUserAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = None


class ApprovalChainAdminViewSet(viewsets.ModelViewSet):
    queryset = ApprovalChain.objects.select_related("workflow_type").prefetch_related("steps__approver")
    serializer_class = ApprovalChainSerializer
    authentication_classes = [JWTStatelessUserAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = None

    @transaction.atomic
    @action(detail=True, methods=["put"], url_path="steps")
    def replace_steps(self, request, pk=None):
        chain = self.get_object()
        serializer = ApprovalStepWriteSerializer(data=request.data.get("steps", []), many=True)
        serializer.is_valid(raise_exception=True)

        ApprovalStep.objects.filter(chain=chain).delete()
        for row in serializer.validated_data:
            ApprovalStep.objects.create(
                chain=chain,
                order=row["order"],
                approver_id=row["approver"],
                role_required=row.get("role_required", ""),
            )

        chain.refresh_from_db()
        return response.Response(self.get_serializer(chain).data)


class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    authentication_classes = [JWTStatelessUserAuthentication]
    permission_classes = [IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        qs = User.objects.order_by("first_name", "last_name", "username")
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role_type=role)
        return qs
