from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.auth_views import MyTokenObtainPairView
from app.swagger import schema_view
from app.views import (DataCenterViewSet, DiskArrayViewSet,
                       MaintenanceRecordViewSet, ServerViewSet, UserViewSet)

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"datacenters", DataCenterViewSet)
router.register(r"servers", ServerViewSet)
router.register(r"disk-arrays", DiskArrayViewSet)
router.register(r"maintenance", MaintenanceRecordViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("api/login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/", include(router.urls)),
]
