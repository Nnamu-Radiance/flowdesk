from rest_framework import permissions, response, status
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.auth.serializers import FlowDeskTokenObtainPairSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = FlowDeskTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return response.Response(UserSerializer(request.user).data)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        return response.Response({"detail": "Logged out"}, status=status.HTTP_200_OK)
