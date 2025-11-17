import logging
from typing import Dict, List, Optional
import ssl
from django.db import transaction

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from django.conf import settings

from app.models import DataCenter, Cluster as DjangoCluster, Network as DjangoNetwork

logger = logging.getLogger(__name__)


class vSphereConnectionManager:
    
    _instance = None
    _service_instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self):
        if self._service_instance is None:
            self._service_instance = self._create_connection()
        return self._service_instance
    
    def _create_connection(self):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            host_port = settings.VSPHERE_SERVER.split(':')
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 443

            service_instance = SmartConnect(
                host=host,
                user=settings.VSPHERE_USER,
                pwd=settings.VSPHERE_PASSWORD,
                port=port,
                sslContext=context
            )
            
            logger.info(f"Connected to vSphere at {settings.VSPHERE_SERVER}")
            return service_instance
        except Exception as e:
            logger.error(f"Failed to connect to vSphere: {str(e)}")
            raise
    
    def disconnect(self):
        if self._service_instance:
            try:
                Disconnect(self._service_instance)
                logger.info("Disconnected from vSphere")
            except Exception as e:
                logger.warning(f"Error during disconnect: {str(e)}")
            finally:
                self._service_instance = None
    
    def get_content(self):
        si = self.get_connection()
        return si.RetrieveContent()


class vSphereSyncService:
    
    def __init__(self):
        self.conn_manager = vSphereConnectionManager()
        self.content = self.conn_manager.get_content()
    
    def _get_container_view(self, obj_type):
        container = self.content.rootFolder
        container_view = self.content.viewManager.CreateContainerView(
            container, [obj_type], recursive=True
        )
        return container_view
    
    def _get_obj_list(self, obj_type):
        view = self._get_container_view(obj_type)
        obj_list = view.view
        view.Destroy()
        return obj_list
    
    def discover_datacenters(self) -> List[Dict]:
        try:
            datacenters = self._get_obj_list(vim.Datacenter)
            discovered = [{
                'vsphere_id': dc._moId,
                'name': dc.name
            } for dc in datacenters]
            logger.info(f"Discovered {len(discovered)} datacenters")
            return discovered
        except Exception as e:
            logger.error(f"Error discovering datacenters: {str(e)}")
            raise
    
    def discover_clusters(self, datacenter_name: Optional[str] = None) -> List[Dict]:
        try:
            clusters = self._get_obj_list(vim.ClusterComputeResource)
            discovered = []
            for cluster in clusters:
                dc = self._get_datacenter_for_obj(cluster)
                if datacenter_name and dc and dc.name != datacenter_name:
                    continue
                config_ex = getattr(cluster.configurationEx, 'drsConfig', None)
                das_config = getattr(cluster.configurationEx, 'dasConfig', None)
                discovered.append({
                    'vsphere_id': cluster._moId,
                    'name': cluster.name,
                    'datacenter_name': dc.name if dc else None,
                    'datacenter_id': dc._moId if dc else None,
                    'total_cpu': getattr(cluster.summary, 'totalCpu', 0),
                    'total_memory': getattr(cluster.summary, 'totalMemory', 0),
                    'num_hosts': getattr(cluster.summary, 'numHosts', 0),
                    'drs_enabled': config_ex.enabled if config_ex else False,
                    'ha_enabled': das_config.enabled if das_config else False,
                })
            logger.info(f"Discovered {len(discovered)} clusters")
            return discovered
        except Exception as e:
            logger.error(f"Error discovering clusters: {str(e)}")
            raise
    
    def discover_networks(self, datacenter_name: Optional[str] = None) -> List[Dict]:
        try:
            networks = self._get_obj_list(vim.Network)
            discovered = []
            for net in networks:
                dc = self._get_datacenter_for_obj(net)
                if datacenter_name and dc and dc.name != datacenter_name:
                    continue
                network_type = 'STANDARD_PORTGROUP'
                if isinstance(net, vim.dvs.DistributedVirtualPortgroup):
                    network_type = 'DISTRIBUTED_PORTGROUP'
                discovered.append({
                    'vsphere_id': net._moId,
                    'name': net.name,
                    'type': network_type,
                    'datacenter_name': dc.name if dc else None,
                })
            logger.info(f"Discovered {len(discovered)} networks")
            return discovered
        except Exception as e:
            logger.error(f"Error discovering networks: {str(e)}")
            raise
    
    def _get_datacenter_for_obj(self, obj):
        current = obj
        while current:
            if isinstance(current, vim.Datacenter):
                return current
            try:
                current = current.parent
            except Exception:
                break
        return None
    
    def _get_cluster_for_host(self, host):
        try:
            parent = host.parent
            if isinstance(parent, vim.ClusterComputeResource):
                return parent
        except Exception:
            pass
        return None
    
    def _get_cluster_for_vm(self, vm):
        try:
            if vm.runtime.host:
                return self._get_cluster_for_host(vm.runtime.host)
        except Exception:
            pass
        return None
    
    @transaction.atomic
    def sync_datacenters(self) -> int:
        logger.info("Starting datacenter sync...")
        discovered = self.discover_datacenters()
        count = 0
        for dc_data in discovered:
            dc, created = DataCenter.objects.update_or_create(
                name=dc_data['name'],
                defaults={'location': f"vSphere ID: {dc_data['vsphere_id']}"}
            )
            count += 1
            action = "Created" if created else "Updated"
            logger.info(f"{action} datacenter: {dc.name}")
        logger.info(f"Datacenter sync completed: {count}")
        return count
    
    @transaction.atomic
    def sync_clusters(self) -> int:
        logger.info("Starting cluster sync...")
        discovered = self.discover_clusters()
        count = 0
        for cluster_data in discovered:
            datacenter = DataCenter.objects.filter(
                name=cluster_data['datacenter_name']
            ).first()
            if not datacenter:
                datacenter = DataCenter.objects.filter(
                    location__contains=cluster_data['datacenter_id']
                ).first()
            if not datacenter:
                logger.warning(f"No datacenter found for cluster {cluster_data['name']}, skipping")
                continue
            description = [
                f"vSphere ID: {cluster_data['vsphere_id']}",
                f"Hosts: {cluster_data['num_hosts']}"
            ]
            if cluster_data.get('drs_enabled'):
                description.append("DRS Enabled")
            if cluster_data.get('ha_enabled'):
                description.append("HA Enabled")
            cluster, created = DjangoCluster.objects.update_or_create(
                name=cluster_data['name'],
                defaults={
                    'datacenter': datacenter,
                    'description': " | ".join(description)
                }
            )
            count += 1
            action = "Created" if created else "Updated"
            logger.info(f"{action} cluster: {cluster.name}")
        logger.info(f"Cluster sync completed: {count}")
        return count
    
    @transaction.atomic
    def sync_networks(self) -> int:
        logger.info("Starting network sync...")
        discovered = self.discover_networks()
        count = 0
        for net_data in discovered:
            datacenter = DataCenter.objects.filter(
                name=net_data['datacenter_name']
            ).first() or DataCenter.objects.first()
            if not datacenter:
                logger.error("No datacenter in DB. Sync datacenters first.")
                continue
            default_cidr = "192.168.0.0/24"
            network, created = DjangoNetwork.objects.update_or_create(
                name=net_data['name'],
                defaults={
                    'datacenter': datacenter,
                    'cidr': default_cidr,
                    'vlan_id': None,
                }
            )
            count += 1
            action = "Created" if created else "Updated"
            logger.info(f"{action} network: {network.name} (type: {net_data['type']})")
        logger.info(f"Network sync completed: {count}")
        return count
    
    def sync_all(self) -> Dict[str, int]:
        logger.info("="*60)
        logger.info("Starting full vSphere inventory sync")
        logger.info("="*60)
        results = {'datacenters': 0, 'clusters': 0, 'networks': 0}
        try:
            results['datacenters'] = self.sync_datacenters()
            results['clusters'] = self.sync_clusters()
            results['networks'] = self.sync_networks()
            logger.info(f"Full sync results: {results}")
        except Exception as e:
            logger.error(f"Full sync failed: {str(e)}")
            raise
        return results
    
    def __del__(self):
        try:
            self.conn_manager.disconnect()
        except Exception:
            pass
