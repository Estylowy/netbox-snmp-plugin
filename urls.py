from django.urls import path
from . import views

urlpatterns = [
    path("interface/<int:interface_id>/fetch/",              views.snmp_interface_fetch,          name="snmp_interface_fetch"),
    path("interface/<int:interface_id>/sync/",               views.snmp_interface_sync,           name="snmp_interface_sync"),
    path("interface/<int:interface_id>/history-by-interface/", views.snmp_history_by_interface,   name="snmp_history_by_interface"),
    path("bulk/",                                            views.snmp_bulk_page,                name="snmp_bulk_page"),
    path("bulk/fetch/",                                      views.snmp_bulk_fetch,               name="snmp_bulk_fetch"),
    path("device/<int:device_id>/history/",                  views.snmp_device_history,           name="snmp_device_history"),
    path("device/<int:device_id>/fetch-interfaces/", views.snmp_device_fetch_interfaces, name="snmp_device_fetch_interfaces"),
    path("device/<int:device_id>/sync-interfaces/",  views.snmp_device_sync_interfaces,  name="snmp_device_sync_interfaces"),
    path("device/<int:device_id>/sync-device/",       views.snmp_device_sync_device,       name="snmp_device_sync_device"),
]