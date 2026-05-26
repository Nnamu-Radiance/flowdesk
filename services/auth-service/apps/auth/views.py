from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from rest_framework import generics, permissions, response, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.auth.permissions import IsAdmin
from apps.auth.serializers import CreateUserSerializer, RoleUpdateSerializer, UserSerializer

User = get_user_model()


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        return response.Response({"detail": "Logged out"}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return response.Response(UserSerializer(request.user).data)


class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by("id")
    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateUserSerializer
        return UserSerializer


class UserRoleUpdateView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, pk: int):
        serializer = RoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.get(pk=pk)
        user.role = serializer.validated_data["role"]
        user.save(update_fields=["role"])
        return response.Response(UserSerializer(user).data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    checks = {"database": "error", "cache": "error"}

    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        pass

    try:
        cache.set("health", "ok", 10)
        checks["cache"] = "ok"
    except Exception:
        pass

    healthy = all(value == "ok" for value in checks.values())
    return response.Response(
        {"status": "healthy" if healthy else "unhealthy", **checks},
        status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
