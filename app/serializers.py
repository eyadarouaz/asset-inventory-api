from rest_framework import serializers

from .models import DataCenter, DiskArray, MaintenanceRecord, Role, Server, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or user.role != Role.ADMIN:
            data.pop("serial_number", None)
        return data

    def validate_serial_number(self, value):
        if Server.objects.filter(serial_number__iexact=value).exists():
            raise serializers.ValidationError(
                "A Server with this serial number already exists."
            )
        return value


class DiskArraySerializer(serializers.ModelSerializer):
    class Meta:
        model = DiskArray
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or user.role != Role.ADMIN:
            data.pop("serial_number", None)
        return data

    def validate_serial_number(self, value):
        if DiskArray.objects.filter(serial_number__iexact=value).exists():
            raise serializers.ValidationError(
                "A Disk Array with this serial number already exists."
            )
        return value


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceRecord
        fields = "__all__"
