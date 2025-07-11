from rest_framework import serializers

from .models import DataCenter, DiskArray, MaintenanceRecord, Server, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "validation_code",
            "code_expires_at",
            "status",
            "role",
        ]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class DataCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataCenter
        fields = "__all__"

    def validate_name(self, value):
        if DataCenter.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError(
                "A DataCenter with this name already exists."
            )
        return value


class ServerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Server
        fields = "__all__"


class DiskArraySerializer(serializers.ModelSerializer):
    class Meta:
        model = DiskArray
        fields = "__all__"


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceRecord
        fields = "__all__"
