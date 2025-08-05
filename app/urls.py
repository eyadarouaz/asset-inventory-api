from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.swagger import schema_view
from app.views.auth_views import MyTokenObtainPairView, get_me, mfa_setup
from app.views.viewsets import (DataCenterViewSet, DiskArrayViewSet,
                                MaintenanceRecordViewSet,
                                ServerDiskArrayMapViewSet, ServerViewSet,
                                UserViewSet)

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"datacenters", DataCenterViewSet)
router.register(r"servers", ServerViewSet)
router.register(r"disk-arrays", DiskArrayViewSet)
router.register(r"maintenance", MaintenanceRecordViewSet)
router.register(r"server-disk", ServerDiskArrayMapViewSet)

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
]
