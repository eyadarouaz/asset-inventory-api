from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import DataCenter, DiskArray, MaintenanceRecord, Server, User
from .serializers import (DataCenterSerializer, DiskArraySerializer,
                          MaintenanceRecordSerializer, ServerSerializer,
                          UserSerializer)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    queryset = User.objects.all()
    serializer_class = UserSerializer


class DataCenterViewSet(viewsets.ModelViewSet):
    queryset = DataCenter.objects.all()
    serializer_class = DataCenterSerializer


class ServerViewSet(viewsets.ModelViewSet):
    queryset = Server.objects.all()
    serializer_class = ServerSerializer


class DiskArrayViewSet(viewsets.ModelViewSet):
    queryset = DiskArray.objects.all()
    serializer_class = DiskArraySerializer


class MaintenanceRecordViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceRecord.objects.all()
    serializer_class = MaintenanceRecordSerializer
