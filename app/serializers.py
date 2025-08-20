from rest_framework import serializers

from .models import (AssetStatus, Cluster, DataCenter, DeploymentJob, DiskArray, MaintenanceRecord, Network, Role, Server,
                     ServerDiskArrayMap, User)


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

class ClusterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cluster
        fields = "__all__"

class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Network
        fields = "__all__"


class ServerSerializer(serializers.ModelSerializer):
    ip_address = serializers.IPAddressField(allow_blank=True, allow_null=True, required=False)

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
    
    def validate(self, attrs):
        # Convert blank string to None
        if attrs.get("ip_address") == "":
            attrs["ip_address"] = None

        status = attrs.get("status", getattr(self.instance, "status", None))
        ip_address = attrs.get("ip_address", getattr(self.instance, "ip_address", None))

        if status == AssetStatus.IN_USE and not ip_address:
            raise serializers.ValidationError({
                "ip_address": "IP address is required when the server is in use."
            })

        if status != AssetStatus.IN_USE and ip_address:
            raise serializers.ValidationError({
                "ip_address": "IP address must be empty when the server is not in use."
            })

        return attrs


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
    resource_type = serializers.SerializerMethodField()
    resource_id = serializers.IntegerField(source="object_id")
    resource_repr = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceRecord
        fields = [
            "id",
            "title",
            "description",
            "performed_at",
            "datacenter",
            "resource_type",
            "resource_id",
            "resource_repr",
        ]

    def get_resource_type(self, obj):
        return obj.content_type.model if obj.content_type else None

    def get_resource_repr(self, obj):
        return str(obj.resource) if obj.resource else None


class ServerDiskArrayMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerDiskArrayMap
        fields = "__all__"

    def validate(self, data):
        if ServerDiskArrayMap.objects.filter(
            server=data["server"], disk_array=data["disk_array"]
        ).exists():
            raise serializers.ValidationError(
                "This server-disk array mapping already exists."
            )
        return data
    
class UnifiedResourceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.CharField()
    content_type_id = serializers.IntegerField()


class DeploymentJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeploymentJob
        fields = '__all__'
        read_only_fields = ['status', 'created_at']



