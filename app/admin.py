from django.contrib import admin
from .models import (
    User,
    DataCenter,
    Cluster,
    Network,
    Server,
    DiskArray,
    ServerDiskArrayMap,
    MaintenanceRecord,
    DeploymentJob,
)

admin.site.register(User)
admin.site.register(DataCenter)
admin.site.register(Cluster)
admin.site.register(Network)
admin.site.register(Server)
admin.site.register(DiskArray)
admin.site.register(ServerDiskArrayMap)
admin.site.register(MaintenanceRecord)
admin.site.register(DeploymentJob)
