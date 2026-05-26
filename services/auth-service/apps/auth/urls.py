from django.urls import path

from apps.auth.views import (
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    UserListCreateView,
    UserRoleUpdateView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("users/", UserListCreateView.as_view(), name="auth-users"),
    path("users/<int:pk>/role/", UserRoleUpdateView.as_view(), name="auth-user-role"),
]
