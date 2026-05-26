from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

menu = PluginMenu(
    label="SNMP Inspector",
    groups=(
        (
            "Narzędzia",
            (
                PluginMenuItem(
                    link="plugins:netbox_snmp_plugin:snmp_bulk_page",
                    link_text="Odpytaj urządzenia",
                    buttons=(
                        PluginMenuButton(
                            link="plugins:netbox_snmp_plugin:snmp_bulk_page",
                            title="Otwórz Odpytaj urządzenia",
                            icon_class="mdi mdi-download-network",
                        ),
                    ),
                ),
            ),
        ),
    ),
    icon_class="mdi mdi-radar",
)
