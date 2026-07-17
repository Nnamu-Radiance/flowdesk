import json
import hashlib
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import signing
from django.db import connection, models
from django.shortcuts import redirect
from rest_framework import generics, permissions, response, status, views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.auth.models import RoleChangeLog
from apps.auth.permissions import IsAdmin
from apps.auth.serializers import (
    AdminUserUpdateSerializer,
    CreateUserSerializer,
    FlowDeskTokenObtainPairSerializer,
    MagicLinkRequestSerializer,
    RoleUpdateSerializer,
    SelfProfileSerializer,
    SignupSerializer,
    UserSerializer,
    validate_email_address,
    normalize_email,
    username_from_email,
)
from apps.auth.tasks import send_magic_link_email

User = get_user_model()
MAGIC_LINK_SALT = "flowdesk.auth.magic-link"
GOOGLE_STATE_SALT = "flowdesk.auth.google-state"
MAGIC_LINK_PREFIX = "magic-link:"
REFRESH_BLACKLIST_PREFIX = "blacklist:"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class LoginView(TokenObtainPairView):
    permission_classes = [permissions.AllowAny]
    serializer_class = FlowDeskTokenObtainPairSerializer


class RefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh", "")
        if not refresh_token:
            return response.Response({"detail": "Refresh token required."}, status=status.HTTP_400_BAD_REQUEST)
        if cache.get(f"{REFRESH_BLACKLIST_PREFIX}{token_hash(refresh_token)}"):
            return response.Response({"detail": "Refresh token has been revoked."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            refresh = RefreshToken(refresh_token)
        except TokenError:
            return response.Response({"detail": "Invalid refresh token."}, status=status.HTTP_401_UNAUTHORIZED)
        return response.Response({"access": str(refresh.access_token)})


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh", "")
        if refresh_token:
            cache.set(
                f"{REFRESH_BLACKLIST_PREFIX}{token_hash(refresh_token)}",
                True,
                timeout=7 * 24 * 60 * 60,
            )
        return response.Response({"detail": "Logged out"}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return response.Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = SelfProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(UserSerializer(request.user).data)


def auth_payload(user):
    refresh = FlowDeskTokenObtainPairSerializer.get_token(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSerializer(user).data,
    }


def get_or_create_identity_user(email, profile=None):
    email = validate_email_address(email)
    profile = profile or {}
    user = User.objects.filter(email__iexact=email).first()
    if user:
        google_id = profile.get("google_id")
        if google_id and not user.google_id:
            user.google_id = google_id
            user.save(update_fields=["google_id"])
        return user

    user = User(
        username=username_from_email(email),
        email=email,
        first_name=profile.get("first_name", ""),
        last_name=profile.get("last_name", ""),
        full_name=profile.get("full_name", ""),
        google_id=profile.get("google_id"),
    )
    user.set_unusable_password()
    user.save()
    return user


class SignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return response.Response(auth_payload(user), status=status.HTTP_201_CREATED)


class MagicLinkRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MagicLinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            token = secrets.token_urlsafe(32)
            cache.set(f"{MAGIC_LINK_PREFIX}{token}", user.id, timeout=settings.MAGIC_LINK_MAX_AGE_SECONDS)
            link = f"{settings.FRONTEND_BASE_URL}/api/auth/magic-link/verify/?token={token}"
            send_magic_link_email.delay(email, link, settings.MAGIC_LINK_MAX_AGE_SECONDS // 60)

        return response.Response(
            {"message": "If that email is registered, a link has been sent."},
            status=status.HTTP_202_ACCEPTED,
        )


class MagicLinkVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.query_params.get("token", "")
        user_id = cache.get(f"{MAGIC_LINK_PREFIX}{token}") if token else None
        if not user_id:
            return response.Response({"detail": "Invalid or expired magic link."}, status=status.HTTP_401_UNAUTHORIZED)
        cache.delete(f"{MAGIC_LINK_PREFIX}{token}")
        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user:
            return response.Response({"detail": "Invalid or expired magic link."}, status=status.HTTP_401_UNAUTHORIZED)

        return response.Response(auth_payload(user))


class GoogleOAuthStartView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET:
            return response.Response(
                {"detail": "Google OAuth is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        state = signing.dumps({"next": request.query_params.get("next", "/")}, salt=GOOGLE_STATE_SALT)
        query = urlencode(
            {
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "online",
                "prompt": "select_account",
                "state": state,
            }
        )
        return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


class GoogleOAuthCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return response.Response({"detail": "Missing Google OAuth code or state."},
                                     status=status.HTTP_400_BAD_REQUEST)

        try:
            signing.loads(state, salt=GOOGLE_STATE_SALT, max_age=600)
            token_payload = self.exchange_code(code)
            google_user = self.fetch_google_user(token_payload["access_token"])
            email = normalize_email(google_user.get("email", ""))
            validate_email_address(email)
        except Exception as exc:
            return response.Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user = get_or_create_identity_user(
            email,
            {
                "first_name": google_user.get("given_name", ""),
                "last_name": google_user.get("family_name", ""),
                "full_name": google_user.get("name", ""),
                "google_id": google_user.get("id") or google_user.get("sub"),
            },
        )
        tokens = auth_payload(user)
        return redirect(
            f"{settings.FRONTEND_BASE_URL}/login/"
            f"#access={tokens['access']}&refresh={tokens['refresh']}"
        )

    def exchange_code(self, code):
        body = urlencode(
            {
                "code": code,
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")
        request = Request(
            "https://oauth2.googleapis.com/token",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as res:
                return json.loads(res.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            raise ValueError("Google token exchange failed.") from exc

    def fetch_google_user(self, access_token):
        request = Request(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=10) as res:
                return json.loads(res.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            raise ValueError("Google profile lookup failed.") from exc


class IsAdminOrInternalService(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.headers.get("X-Internal-Service"):
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", "") == "admin"
        )


class IsAuthenticatedOrInternalService(permissions.BasePermission):
    """Allows any authenticated user OR internal service calls (no JWT required)."""

    def has_permission(self, request, view):
        if request.headers.get("X-Internal-Service"):
            return True
        return bool(request.user and request.user.is_authenticated)


class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by("id")

    def get_permissions(self):
        # GET: any authenticated user (supervisor dropdown) OR internal services (resolve_approver)
        # POST: admins and internal services only
        if self.request.method == "GET":
            return [IsAuthenticatedOrInternalService()]
        return [IsAdminOrInternalService()]

    def get_queryset(self):
        qs = User.objects.all().order_by("id")
        role = self.request.query_params.get("role")
        approver_type = self.request.query_params.get("approver_type")
        is_active = self.request.query_params.get("is_active")
        department = self.request.query_params.get("department")
        faculty = self.request.query_params.get("faculty")
        search = self.request.query_params.get("search")

        if role:
            qs = qs.filter(role=role)
        if approver_type:
            qs = qs.filter(approver_type=approver_type)
        if is_active is not None:
            qs = qs.filter(is_active=str(is_active).lower() in {"1", "true", "yes"})
        if department:
            qs = qs.filter(department__iexact=department)
        if faculty:
            qs = qs.filter(faculty__iexact=faculty)
        if search:
            qs = qs.filter(
                models.Q(full_name__icontains=search)
                | models.Q(first_name__icontains=search)
                | models.Q(last_name__icontains=search)
                | models.Q(matricule__icontains=search)
                | models.Q(email__icontains=search)
            )
        return qs

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateUserSerializer
        return UserSerializer


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all().order_by("id")
    permission_classes = [IsAdminOrInternalService]

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return AdminUserUpdateSerializer
        return UserSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class SignatureStampUploadView(views.APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def can_manage_stamp(self, user):
        return getattr(user, "role", "") in {"approver", "admin"}

    def patch(self, request):
        user = request.user
        update_fields = []
        if "signature_image" in request.FILES:
            if request.FILES["signature_image"].size > 200 * 1024:
                return response.Response({"detail": "Signature must be under 200KB."},
                                         status=status.HTTP_400_BAD_REQUEST)
            user.signature_image = request.FILES["signature_image"]
            update_fields.append("signature_image")
        if "stamp_image" in request.FILES:
            if not self.can_manage_stamp(user):
                return response.Response(
                    {"detail": "Submitters cannot upload an official stamp."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if request.FILES["stamp_image"].size > 200 * 1024:
                return response.Response({"detail": "Stamp must be under 200KB."}, status=status.HTTP_400_BAD_REQUEST)
            user.stamp_image = request.FILES["stamp_image"]
            update_fields.append("stamp_image")
        if update_fields:
            user.save(update_fields=update_fields)
        return response.Response(UserSerializer(user).data)

    def delete(self, request):
        field = request.query_params.get("field")
        user = request.user
        if field == "signature_image":
            user.signature_image = None
        elif field == "stamp_image":
            if not self.can_manage_stamp(user):
                return response.Response(
                    {"detail": "Submitters cannot delete an official stamp."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            user.stamp_image = None
        else:
            return response.Response({"detail": "field must be signature_image or stamp_image"},
                                     status=status.HTTP_400_BAD_REQUEST)
        user.save(update_fields=[field])
        return response.Response({"detail": "Deleted."})


class UserRoleUpdateView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, pk: int):
        serializer = RoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return response.Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        old_role = user.role
        old_approver_type = user.approver_type or ""

        new_role = serializer.validated_data["role"]
        new_approver_type = serializer.validated_data.get("approver_type") or ""

        user.role = new_role
        user.approver_type = new_approver_type if new_role == "approver" else None
        user.save(update_fields=["role", "approver_type"])

        RoleChangeLog.objects.create(
            user=user,
            changed_by=request.user,
            old_role=old_role,
            new_role=new_role,
            old_approver_type=old_approver_type,
            new_approver_type=new_approver_type,
        )

        return response.Response(UserSerializer(user).data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_check(request):
    checks = {"database": "error", "cache": "error"}
    details = {}

    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception as exc:
        details["database"] = str(exc)

    try:
        cache.set("health", "ok", 10)
        checks["cache"] = "ok"
    except Exception as exc:
        details["cache"] = str(exc)

    healthy = all(value == "ok" for value in checks.values())
    payload = {"status": "healthy" if healthy else "unhealthy", **checks}
    if details:
        payload["details"] = details
    return response.Response(
        payload,
        status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
