from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.swagger import schema_view
from app.views.auth_views import MyTokenObtainPairView, get_me, mfa_setup
from app.views.deployment_views import DeploymentDestroyView, DeploymentExecuteView, DeploymentJobDetailView, DeploymentJobLogsView, DeploymentJobView, DeploymentPlanView, DeploymentStatusView
from app.views.viewsets import (ClusterViewSet, DataCenterViewSet, DiskArrayViewSet,
                                MaintenanceRecordViewSet, NetworkViewSet,
                                ServerDiskArrayMapViewSet, ServerViewSet,
                                UserViewSet, get_datacenter_resources)
from app.views.sync_views import (
    sync_vsphere_inventory,
    vsphere_info,
    discover_vsphere_resources
)

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"datacenters", DataCenterViewSet)
router.register(r"servers", ServerViewSet)
router.register(r"disk-arrays", DiskArrayViewSet)
router.register(r"maintenance", MaintenanceRecordViewSet)
router.register(r"server-disk", ServerDiskArrayMapViewSet)
router.register(r'networks', NetworkViewSet)
router.register(r'clusters', ClusterViewSet)

urlpatterns = [

    # Admin 
    path("admin/", admin.site.urls),

    # Swagger
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),

    # Auth
    path("api/login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/me/", get_me, name="get-me"),
    path("api/mfa/setup/", mfa_setup, name="mfa_setup"),

    # Router URLs
    path("api/", include(router.urls)),

    # Datacenter resources
    path('api/datacenters/<int:id>/resources/', get_datacenter_resources, name='datacenter-resources'),

    # ==================== Deployment Endpoints ====================
    # Deployment Workflow
    path("api/deployments/", DeploymentJobView.as_view(), name="deployment-jobs"),
    path("api/deployments/<int:job_id>/", DeploymentJobDetailView.as_view(), name="deployment-detail"),

    path("api/deployments/<int:job_id>/plan/", DeploymentPlanView.as_view(), name="deployment-plan"),
    path("api/deployments/<int:job_id>/execute/", DeploymentExecuteView.as_view(), name="deployment-execute"),
    path("api/deployments/<int:job_id>/destroy/", DeploymentDestroyView.as_view(), name="deployment-destroy"),

        path("api/deployments/<int:job_id>/status/", DeploymentStatusView.as_view(), name="deployment-status"),
    path("api/deployments/<int:job_id>/logs/", DeploymentJobLogsView.as_view(), name="deployment-logs"),

    # ==================== Sync Endpoints ====================
    # Full inventory sync
    path('api/sync/', sync_vsphere_inventory, name='sync-vsphere-all'),

    # vSphere info and discovery
    path('api/vsphere-info/', vsphere_info, name='vsphere-info'),
    path('api/discover-vsphere/', discover_vsphere_resources, name='discover-vsphere'),

]
