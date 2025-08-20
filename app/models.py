import pyotp
import ipaddress

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


# ==============================
# Constants and Choices
# ==============================

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


# ==============================
# User and Authentication
# ==============================

class User(AbstractUser):
    validation_code = models.CharField(max_length=100, null=True, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=UserStatus.choices, default=UserStatus.INACTIVE
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.OPERATOR)
    mfa_enabled = models.BooleanField(default=True)
    totp_secret = models.CharField(max_length=32, blank=True, null=True)

    def generate_totp_secret(self):
        if not self.totp_secret:
            self.totp_secret = pyotp.random_base32()
            self.save()

    def __str__(self):
        return self.username

# ==============================
# Core Physical Infrastructure
# ==============================

class DataCenter(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    admins = models.ManyToManyField(User, related_name="datacenters")

    def __str__(self):
        return self.name
    
class Cluster(models.Model):
    name = models.CharField(max_length=100, unique=True)
    datacenter = models.ForeignKey(DataCenter, related_name="clusters", on_delete=models.CASCADE)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Network(models.Model):
    name = models.CharField(max_length=100)
    vlan_id = models.PositiveIntegerField(null=True, blank=True)
    cidr = models.CharField(max_length=32)  # e.g. "192.168.1.0/24"
    gateway = models.GenericIPAddressField(protocol="IPv4", null=True, blank=True)
    datacenter = models.ForeignKey(DataCenter, related_name="networks", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} ({self.cidr})"

    def get_subnet(self):
        return ipaddress.ip_network(self.cidr)

    def is_ip_in_subnet(self, ip):
        return ipaddress.ip_address(ip) in self.get_subnet()

    def is_ip_assigned(self, ip):
        return self.servers.filter(ip_address=ip).exists()

    def validate_ip(self, ip):
        if not self.is_ip_in_subnet(ip):
            raise ValidationError(f"{ip} is not within subnet {self.cidr}")
        if self.is_ip_assigned(ip):
            raise ValidationError(f"{ip} is already assigned in {self.name}")
        
    def clean(self):
        try:
            ipaddress.ip_network(self.cidr)
        except ValueError:
            raise ValidationError(f"Invalid CIDR: {self.cidr}")


# ==============================
# Resource Base and Subtypes
# ==============================

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
    cpu = models.PositiveIntegerField()
    ram = models.PositiveIntegerField()
    ip_address = models.GenericIPAddressField(
        protocol="both",
        blank=True,
        null=True
    )
    datacenter = models.ForeignKey(
        DataCenter, related_name="servers", on_delete=models.CASCADE
    )
    cluster = models.ForeignKey(
        Cluster, related_name="servers", on_delete=models.SET_NULL, null=True, blank=True
    )
    network = models.ForeignKey(
        Network, related_name="servers", on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Server: {self.serial_number}"
    
    def clean(self):
        if self.ip_address and self.network:
            self.network.validate_ip(self.ip_address)


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

# ==============================
# Maintenance Tracking
# ==============================


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

# ==============================
# VM Deployment Jobs
# ==============================

class DeploymentJob(models.Model):
    name = models.CharField(max_length=255)
    vm_name = models.CharField(max_length=255)
    vm_count = models.IntegerField(default=1)

    cpu = models.IntegerField(default=2)
    memory = models.IntegerField(default=2048)  # MB

    datacenter = models.ForeignKey("DataCenter", on_delete=models.CASCADE)
    cluster = models.ForeignKey("Cluster", null=True, blank=True, on_delete=models.SET_NULL)
    network = models.ForeignKey("Network", null=True, blank=True, on_delete=models.SET_NULL)

    datastore = models.CharField(max_length=255, default="LocalDS_0")

    minio_object = models.CharField(max_length=255, null=True, blank=True)
    plan_output = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.vm_name})"



