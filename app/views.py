from rest_framework import viewsets

from .models import DataCenter, DiskArray, MaintenanceRecord, Server, User
from .permissions import IsAdminOnly, IsAdminOrReadOnly
from .serializers import (
    DataCenterSerializer,
    DiskArraySerializer,
    MaintenanceRecordSerializer,
    ServerSerializer,
    UserSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOnly]
    queryset = User.objects.all()
    serializer_class = UserSerializer


class DataCenterViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = DataCenter.objects.all()
    serializer_class = DataCenterSerializer


class ServerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Server.objects.all()
    serializer_class = ServerSerializer


class DiskArrayViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = DiskArray.objects.all()
    serializer_class = DiskArraySerializer


class MaintenanceRecordViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = MaintenanceRecord.objects.all()
    serializer_class = MaintenanceRecordSerializer
