from netbox.plugins import PluginTemplateExtension
from dcim.models import Device, Interface
import re


class InterfaceSNMPButton(PluginTemplateExtension):
    """Niebieski SNMP — na stronie interfejsu i zakładce Interfaces urządzenia."""
    model = "dcim.interface"

    def buttons(self):
        obj = self.context["object"]
        if not isinstance(obj, Interface):
            return ""
        return self.render(
            "netbox_snmp_plugin/snmp_interface_single_button.html",
            extra_context={"interface": obj, "device": obj.device},
        )


class DeviceGreenButton(PluginTemplateExtension):
    """Zielony SNMP Device — tylko na głównej zakładce Device."""
    model = "dcim.device"

    def buttons(self):
        obj = self.context["object"]
        if not isinstance(obj, Device):
            return ""
        # Sprawdź czy jesteśmy na głównej zakładce Device
        request = self.context.get("request")
        if request and not re.search(r'/dcim/devices/\d+/$', request.path):
            return ""
        return self.render(
            "netbox_snmp_plugin/snmp_device_sysinfo_button.html",
            extra_context={"device": obj},
        )

    def right_page(self):
        obj = self.context["object"]
        if not isinstance(obj, Device):
            return ""
        return self.render(
            "netbox_snmp_plugin/snmp_device_panel.html",
            extra_context={"device": obj},
        )


class DeviceInterfacesButton(PluginTemplateExtension):
    """Niebieski SNMP — na zakładce Interfaces urządzenia."""
    model = "dcim.device"

    def buttons(self):
        obj = self.context["object"]
        if not isinstance(obj, Device):
            return ""
        request = self.context.get("request")
        if request and not re.search(r'/dcim/devices/\d+/interfaces/', request.path):
            return ""
        return self.render(
            "netbox_snmp_plugin/snmp_device_button.html",
            extra_context={"device": obj},
        )


template_extensions = [InterfaceSNMPButton, DeviceGreenButton, DeviceInterfacesButton]
