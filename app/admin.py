from django.contrib import admin
from .models import User, DataCenter, Server, DiskArray, MaintenanceRecord

admin.site.register(User)
admin.site.register(DataCenter)
admin.site.register(Server)
admin.site.register(DiskArray)
admin.site.register(MaintenanceRecord)