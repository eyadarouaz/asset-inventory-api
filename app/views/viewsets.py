from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType

from ..models import (DataCenter, DiskArray, MaintenanceRecord, Server,
                      ServerDiskArrayMap, User)
from ..permissions import IsAdminOnly, IsAdminOrReadOnly
from ..serializers import (DataCenterSerializer, DiskArraySerializer,
                           MaintenanceRecordSerializer,
                           ServerDiskArrayMapSerializer, ServerSerializer, UnifiedResourceSerializer,
                           UserSerializer)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated


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

    @action(detail=False, methods=["get"], url_path="by-datacenter/(?P<datacenter_id>[^/.]+)")
    def by_datacenter(self, request, datacenter_id=None):
        records = MaintenanceRecord.objects.filter(datacenter_id=datacenter_id)
        serializer = self.get_serializer(records, many=True)
        return Response(serializer.data)


class ServerDiskArrayMapViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = ServerDiskArrayMap.objects.all()
    serializer_class = ServerDiskArrayMapSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_datacenter_resources(request, id):
    try:
        datacenter = DataCenter.objects.get(pk=id)
    except DataCenter.DoesNotExist:
        return Response({'detail': 'DataCenter not found.'}, status=404)

    resources = []

    # Server resources
    servers = Server.objects.filter(datacenter=datacenter)
    ct_server = ContentType.objects.get_for_model(Server)
    for server in servers:
        resources.append({
            "id": server.id,
            "name": f"Server: {server.serial_number}",
            "type": "server",
            "content_type_id": ct_server.id
        })

    # DiskArray resources
    disk_arrays = DiskArray.objects.filter(datacenter=datacenter)
    ct_disk_array = ContentType.objects.get_for_model(DiskArray)
    for da in disk_arrays:
        resources.append({
            "id": da.id,
            "name": f"DiskArray: {da.serial_number}",
            "type": "diskarray",
            "content_type_id": ct_disk_array.id
        })

    serializer = UnifiedResourceSerializer(resources, many=True)
    return Response(serializer.data)

