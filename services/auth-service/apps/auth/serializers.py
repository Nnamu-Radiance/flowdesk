from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email as django_validate_email
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.auth.models import RoleChangeLog

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


def username_from_email(email: str) -> str:
    return email.split("@", 1)[0].replace(".", "_")


class UserSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    display_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email",
            "first_name", "last_name", "full_name",
            "matricule", "faculty", "department", "phone_number",
            "profile_picture", "signature_image", "stamp_image", "google_id",
            "role", "approver_type", "display_role",
            "is_active",
        ]
        read_only_fields = ["id", "username", "google_id", "role", "approver_type", "is_active"]

    def get_display_role(self, obj):
        return obj.display_role()


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    matricule = serializers.CharField(required=False, allow_blank=True, max_length=50)
    faculty = serializers.CharField(required=False, allow_blank=True, max_length=200)
    department = serializers.CharField(required=False, allow_blank=True, max_length=200)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate_email(self, value):
        email = validate_email_address(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account already exists for this email.")
        return email

    def create(self, validated_data):
        password = validated_data.pop("password")
        email = validated_data["email"]
        if not validated_data.get("full_name"):
            validated_data["full_name"] = " ".join(
                value for value in [validated_data.get("first_name", ""), validated_data.get("last_name", "")] if value
            )
        if not validated_data.get("matricule"):
            validated_data.pop("matricule", None)
        user = User(username=username_from_email(email), **validated_data)
        user.set_password(password)
        user.save()
        return user


class CreateUserSerializer(SignupSerializer):
    password = serializers.CharField(write_only=True, min_length=8, required=False)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    approver_type = serializers.ChoiceField(
        choices=User.ApproverType.choices,
        required=False,
        allow_null=True,
    )

    def validate(self, data):
        role = data.get("role")
        approver_type = data.get("approver_type")
        if role == "approver" and not approver_type:
            raise serializers.ValidationError(
                {"approver_type": "approver_type is required when role is 'approver'."}
            )
        return data

    def create(self, validated_data):
        password = validated_data.pop("password", None) or User.objects.make_random_password(length=14)
        approver_type = validated_data.pop("approver_type", None)
        user = super().create({**validated_data, "password": password})
        user.role = validated_data["role"]
        user.approver_type = approver_type if validated_data["role"] == "approver" else ""
        user.save(update_fields=["role", "approver_type"])
        user._temporary_password = password
        return user


class MagicLinkRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return validate_email_address(value)


class RoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    approver_type = serializers.ChoiceField(
        choices=User.ApproverType.choices,
        required=False,
        allow_null=True,
    )

    def validate(self, data):
        role = data.get("role")
        approver_type = data.get("approver_type")

        if role == "approver" and not approver_type:
            raise serializers.ValidationError(
                {"approver_type": "approver_type is required when role is 'approver'."}
            )
        if role != "approver" and approver_type:
            raise serializers.ValidationError(
                {"approver_type": "approver_type must be empty for non-approver roles."}
            )
        return data


class SignatureStampUploadSerializer(serializers.Serializer):
    signature_image = serializers.ImageField(required=False, allow_null=True)
    stamp_image = serializers.ImageField(required=False, allow_null=True)


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "full_name",
            "matricule",
            "faculty",
            "department",
            "phone_number",
            "is_active",
        ]

    def validate_matricule(self, value):
        # Empty string would violate the unique constraint; treat it as NULL.
        return value.strip() if value and value.strip() else None


class SelfProfileSerializer(AdminUserUpdateSerializer):
    class Meta(AdminUserUpdateSerializer.Meta):
        fields = [
            "email",
            "first_name",
            "last_name",
            "full_name",
            "matricule",
            "faculty",
            "department",
            "phone_number",
        ]


class RoleChangeLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True)

    class Meta:
        model = RoleChangeLog
        fields = ["id", "old_role", "new_role", "changed_by", "changed_by_name", "changed_at"]


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
        token["user_id"] = user.id
        token["role"] = user.role
        token["approver_type"] = user.approver_type or ""
        token["full_name"] = user.full_name or user.get_full_name()
        token["matricule"] = user.matricule or ""
        token["faculty"] = user.faculty
        token["department"] = user.department
        return token
