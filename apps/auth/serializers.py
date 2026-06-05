from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email as django_validate_email
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.auth.models import CustomUser

User = get_user_model()


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def validate_email_address(value: str) -> str:
    email = normalize_email(value)
    try:
        django_validate_email(email)
    except DjangoValidationError as exc:
        raise serializers.ValidationError("Enter a valid email address.") from exc
    return email


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role_type",
            "department",
        ]


class FlowDeskTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        identifier = normalize_email(attrs.get(self.username_field, ""))
        if "@" in identifier:
            validate_email_address(identifier)
            try:
                user = User.objects.get(email__iexact=identifier)
            except User.DoesNotExist as exc:
                raise serializers.ValidationError("No account exists for this email.") from exc
            attrs[self.username_field] = user.get_username()

        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = getattr(user, "role_type", "")
        token["department"] = user.department
        return token
