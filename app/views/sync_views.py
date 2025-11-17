from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from app.vsphere_sync import vSphereSyncService
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_vsphere_inventory(request):
    try:
        sync_service = vSphereSyncService()
        results = sync_service.sync_all()
        
        return Response({
            'success': True,
            'message': 'Inventory synced successfully from vSphere',
            'results': results
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_datacenters(request):
    try:
        sync_service = vSphereSyncService()
        count = sync_service.sync_datacenters()
        
        return Response({
            'success': True,
            'message': f'Synced {count} datacenters',
            'count': count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Datacenter sync failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_clusters(request):
    try:
        sync_service = vSphereSyncService()
        count = sync_service.sync_clusters()
        
        return Response({
            'success': True,
            'message': f'Synced {count} clusters',
            'count': count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Cluster sync failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_networks(request):
    try:
        sync_service = vSphereSyncService()
        count = sync_service.sync_networks()
        
        return Response({
            'success': True,
            'message': f'Synced {count} networks',
            'count': count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Network sync failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@cache_page(60)  # Cache for 1 minute
def vsphere_info(request):
    try:
        sync_service = vSphereSyncService()
        info = sync_service.get_vsphere_info()
        
        return Response(info, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Failed to get vSphere info: {str(e)}")
        return Response({
            'connected': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def discover_vsphere_resources(request):
    resource_type = request.query_params.get('resource_type', 'datacenters')
    
    try:
        sync_service = vSphereSyncService()
        
        if resource_type == 'datacenters':
            resources = sync_service.discover_datacenters()
        elif resource_type == 'clusters':
            resources = sync_service.discover_clusters()
        elif resource_type == 'networks':
            resources = sync_service.discover_networks()
        elif resource_type == 'vms':
            resources = sync_service.discover_vms()
        elif resource_type == 'hosts':
            resources = sync_service.discover_hosts()
        else:
            return Response({
                'error': f'Invalid resource_type: {resource_type}',
                'valid_types': ['datacenters', 'clusters', 'networks', 'vms', 'hosts']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'resource_type': resource_type,
            'count': len(resources),
            'resources': resources
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Discovery failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def datacenter_sync_action(self, request):
    try:
        sync_service = vSphereSyncService()
        count = sync_service.sync_datacenters()
        
        return Response({
            'success': True,
            'message': f'Synced {count} datacenters',
            'count': count
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def cluster_sync_action(self, request):
    try:
        sync_service = vSphereSyncService()
        count = sync_service.sync_clusters()
        
        return Response({
            'success': True,
            'message': f'Synced {count} clusters',
            'count': count
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def network_sync_action(self, request):
    try:
        sync_service = vSphereSyncService()
        count = sync_service.sync_networks()
        
        return Response({
            'success': True,
            'message': f'Synced {count} networks',
            'count': count
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DataCenterViewSetWithSync(viewsets.ModelViewSet):
    
    @action(detail=False, methods=['post'], url_path='sync-from-vsphere')
    def sync_from_vsphere(self, request):
        """Sync datacenters from vSphere"""
        return datacenter_sync_action(self, request)
    
    @action(detail=True, methods=['post'], url_path='sync-resources')
    def sync_datacenter_resources(self, request, pk=None):
        """Sync clusters and networks for a specific datacenter"""
        datacenter = self.get_object()
        
        try:
            sync_service = vSphereSyncService()
            
            # Discover datacenter's resources from vSphere
            discovered_dcs = sync_service.discover_datacenters()
            dc_vsphere_id = None
            
            # Find vSphere ID for this datacenter
            for dc in discovered_dcs:
                if dc['name'] == datacenter.name:
                    dc_vsphere_id = dc['vsphere_id']
                    break
            
            if not dc_vsphere_id:
                return Response({
                    'success': False,
                    'error': f'Datacenter {datacenter.name} not found in vSphere'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Sync clusters and networks for this datacenter
            clusters = sync_service.discover_clusters(dc_vsphere_id)
            networks = sync_service.discover_networks(dc_vsphere_id)
            
            return Response({
                'success': True,
                'datacenter': datacenter.name,
                'clusters': len(clusters),
                'networks': len(networks),
                'resources': {
                    'clusters': clusters,
                    'networks': networks
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to sync datacenter resources: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
