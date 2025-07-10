from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    OPERATOR = "operator", "Operator"

class Status(models.TextChoices):
    INACTIVE = "inactive", "Inactive"
    ACTIVE = "active", "Active"

class User(AbstractUser):
    validation_code = models.CharField(max_length=100, null=True, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.INACTIVE
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.OPERATOR
    )


class DataCenter(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    admin = models.ForeignKey(User, related_name='datacenters', on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class MaintenanceRecord(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    performed_at = models.DateTimeField(default=timezone.now)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    resource = GenericForeignKey('content_type', 'object_id')

    datacenter = models.ForeignKey(DataCenter, related_name='maintenance_records', on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.title} ({self.performed_at})"


class Resource(models.Model):
    serial_number = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=100)
    storage = models.PositiveIntegerField()

    class Meta:
        abstract = True


class Server(Resource):
    ip_address = models.GenericIPAddressField(protocol='both')
    cpu = models.PositiveIntegerField()
    ram = models.PositiveIntegerField()

    datacenter = models.ForeignKey(DataCenter, related_name='servers', on_delete=models.CASCADE)

    def __str__(self):
        return f"Server: {self.serial_number}"


class DiskArray(Resource):
    datacenter = models.ForeignKey(DataCenter, related_name='disk_arrays', on_delete=models.CASCADE)

    def __str__(self):
        return f"DiskArray: {self.serial_number}"
