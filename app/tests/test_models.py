from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from app.models import (
    User, Role, UserStatus, AssetStatus, ConnectionType,
    DataCenter, MaintenanceRecord, Server, DiskArray, ServerDiskArrayMap
)


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(username="testuser", password="password123")
        self.assertEqual(user.status, UserStatus.INACTIVE)
        self.assertEqual(user.role, Role.OPERATOR)
        self.assertTrue(user.mfa_enabled)
        self.assertIsNone(user.totp_secret)

    def test_generate_totp_secret(self):
        user = User.objects.create_user(username="testuser", password="password123")
        self.assertIsNone(user.totp_secret)
        user.generate_totp_secret()
        self.assertIsNotNone(user.totp_secret)
        self.assertEqual(len(user.totp_secret), 32)


class DataCenterModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="adminpass")
        self.datacenter = DataCenter.objects.create(name="DC1", location="New York")
        self.datacenter.admins.add(self.user)

    def test_datacenter_creation(self):
        self.assertEqual(self.datacenter.name, "DC1")
        self.assertIn(self.user, self.datacenter.admins.all())


class ServerAndDiskArrayModelTest(TestCase):
    def setUp(self):
        self.datacenter = DataCenter.objects.create(name="DC1", location="Berlin")

    def test_server_creation(self):
        server = Server.objects.create(
            serial_number="SRV123",
            model="Dell R740",
            manufacturer="Dell",
            storage=2048,
            ip_address="192.168.1.100",
            cpu=16,
            ram=128,
            datacenter=self.datacenter
        )
        self.assertEqual(server.status, AssetStatus.AVAILABLE)
        self.assertEqual(str(server), "Server: SRV123")

    def test_disk_array_creation(self):
        array = DiskArray.objects.create(
            serial_number="DA456",
            model="NetApp FAS",
            manufacturer="NetApp",
            storage=4096,
            datacenter=self.datacenter
        )
        self.assertEqual(str(array), "DiskArray: DA456")


class ServerDiskArrayMapTest(TestCase):
    def setUp(self):
        self.datacenter = DataCenter.objects.create(name="DC1", location="Tokyo")
        self.server = Server.objects.create(
            serial_number="SRV123",
            model="HP ProLiant",
            manufacturer="HP",
            storage=1024,
            ip_address="10.0.0.1",
            cpu=8,
            ram=64,
            datacenter=self.datacenter
        )
        self.disk_array = DiskArray.objects.create(
            serial_number="DA456",
            model="EMC VNX",
            manufacturer="EMC",
            storage=2048,
            datacenter=self.datacenter
        )

    def test_mapping_creation(self):
        mapping = ServerDiskArrayMap.objects.create(
            server=self.server,
            disk_array=self.disk_array,
            connection_type=ConnectionType.FIBRE,
            mount_point="/mnt/storage"
        )
        self.assertEqual(mapping.connection_type, ConnectionType.FIBRE)
        self.assertEqual(str(mapping), "SRV123 ↔ DA456")

    def test_unique_constraint(self):
        ServerDiskArrayMap.objects.create(
            server=self.server,
            disk_array=self.disk_array,
            connection_type=ConnectionType.ISCSI
        )
        with self.assertRaises(Exception):
            ServerDiskArrayMap.objects.create(
                server=self.server,
                disk_array=self.disk_array,
                connection_type=ConnectionType.NFS
            )


class MaintenanceRecordTest(TestCase):
    def setUp(self):
        self.datacenter = DataCenter.objects.create(name="DC1", location="Paris")
        self.server = Server.objects.create(
            serial_number="SRV789",
            model="Supermicro",
            manufacturer="Supermicro",
            storage=512,
            ip_address="172.16.0.1",
            cpu=4,
            ram=32,
            datacenter=self.datacenter
        )

    def test_maintenance_record_creation(self):
        content_type = ContentType.objects.get_for_model(Server)
        record = MaintenanceRecord.objects.create(
            title="Firmware Upgrade",
            description="Upgraded firmware to version X.Y.Z",
            content_type=content_type,
            object_id=self.server.id,
            datacenter=self.datacenter
        )
        self.assertEqual(record.resource, self.server)
        self.assertIn("Firmware Upgrade", str(record))
