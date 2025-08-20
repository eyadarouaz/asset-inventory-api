from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.swagger import schema_view
from app.views.auth_views import MyTokenObtainPairView, get_me, mfa_setup
from app.views.deployment_views import DeploymentJobLogsView, DeploymentJobView
from app.views.viewsets import (ClusterViewSet, DataCenterViewSet, DiskArrayViewSet,
                                MaintenanceRecordViewSet, NetworkViewSet,
                                ServerDiskArrayMapViewSet, ServerViewSet,
                                UserViewSet, get_datacenter_resources)

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
    path("admin/", admin.site.urls),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("api/login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/me/", get_me, name="get-me"),
    path("api/mfa/setup/", mfa_setup, name="mfa_setup"),
    path("api/", include(router.urls)),
    path("api/deployments/", DeploymentJobView.as_view(), name="create-deployment"),
    path("api/deployments/<int:job_id>/logs/", DeploymentJobLogsView.as_view(), name="deployment-logs"),
    path('api/datacenters/<int:id>/resources/', get_datacenter_resources, name='datacenter-resources'),
]
