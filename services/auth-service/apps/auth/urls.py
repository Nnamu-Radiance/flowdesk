from django.urls import path

from apps.auth.views import (
    SignatureStampUploadView,
    GoogleOAuthCallbackView,
    GoogleOAuthStartView,
    LoginView,
    LogoutView,
    MagicLinkRequestView,
    MagicLinkVerifyView,
    MeView,
    RefreshView,
    SignatureStampUploadView,
    SignupView,
    UserListCreateView,
    UserDetailView,
    UserRoleUpdateView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("magic/request/", MagicLinkRequestView.as_view(), name="auth-magic-request"),
    path("magic/verify/", MagicLinkVerifyView.as_view(), name="auth-magic-verify"),
    path("magic-link/request/", MagicLinkRequestView.as_view(), name="auth-magic-link-request"),
    path("magic-link/verify/", MagicLinkVerifyView.as_view(), name="auth-magic-link-verify"),
    path("google/", GoogleOAuthStartView.as_view(), name="auth-google"),
    path("google/start/", GoogleOAuthStartView.as_view(), name="auth-google-start"),
    path("google/callback/", GoogleOAuthCallbackView.as_view(), name="auth-google-callback"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("profile/signature-stamp/", SignatureStampUploadView.as_view(), name="signature-stamp-upload"),
    path("users/", UserListCreateView.as_view(), name="auth-users"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="auth-user-detail"),
    path("users/<int:pk>/role/", UserRoleUpdateView.as_view(), name="auth-user-role"),
]
