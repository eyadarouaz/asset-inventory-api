from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    OPERATOR = "operator", "Operator"


class UserStatus(models.TextChoices):
    INACTIVE = "inactive", "Inactive"
    ACTIVE = "active", "Active"


class AssetStatus(models.TextChoices):
    IN_USE = "in_use", "In Use"
    MAINTENANCE = "maintenance", "Maintenance"
    AVAILABLE = "available", "Available"


class ConnectionType(models.TextChoices):
    ISCSI = "iscsi", "iSCSI"
    FIBRE = "fibre", "Fibre Channel"
    NFS = "nfs", "NFS"
    SMB = "smb", "SMB"
    SAS = "sas", "SAS"
    OTHER = "other", "Other"


class User(AbstractUser):
    validation_code = models.CharField(max_length=100, null=True, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=UserStatus.choices, default=UserStatus.INACTIVE
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.OPERATOR)

    def __str__(self):
        return self.username


class DataCenter(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    admins = models.ManyToManyField(User, related_name="datacenters")

    def __str__(self):
        return self.name


class MaintenanceRecord(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    performed_at = models.DateTimeField(default=timezone.now)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    resource = GenericForeignKey("content_type", "object_id")

    datacenter = models.ForeignKey(
        DataCenter, related_name="maintenance_records", on_delete=models.CASCADE
    )

    def __str__(self):
        return f"{self.title} ({self.performed_at})"


class Resource(models.Model):
    serial_number = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=100)
    storage = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=AssetStatus.choices,
        default=AssetStatus.AVAILABLE,
    )

    class Meta:
        abstract = True


class Server(Resource):
    ip_address = models.GenericIPAddressField(protocol="both")
    cpu = models.PositiveIntegerField()
    ram = models.PositiveIntegerField()

    datacenter = models.ForeignKey(
        DataCenter, related_name="servers", on_delete=models.CASCADE
    )

    def __str__(self):
        return f"Server: {self.serial_number}"


class DiskArray(Resource):
    datacenter = models.ForeignKey(
        DataCenter, related_name="disk_arrays", on_delete=models.CASCADE
    )

    def __str__(self):
        return f"DiskArray: {self.serial_number}"


class ServerDiskArrayMap(models.Model):
    server = models.ForeignKey(
        Server, related_name="disk_array_links", on_delete=models.CASCADE
    )
    disk_array = models.ForeignKey(
        DiskArray, related_name="server_links", on_delete=models.CASCADE
    )
    connection_type = models.CharField(
        max_length=10, choices=ConnectionType.choices, default=ConnectionType.ISCSI
    )
    mount_point = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        unique_together = ("server", "disk_array")

    def __str__(self):
        return f"{self.server.serial_number} ↔ {self.disk_array.serial_number}"
