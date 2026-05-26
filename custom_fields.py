"""
Rejestruje custom fields na modelu Device przy starcie pluginu.
Pola przechowują: credentials SNMP per-device + historia ostatniego odpytania.
"""
import logging

logger = logging.getLogger("netbox.plugins.netbox_snmp_plugin")

CUSTOM_FIELDS = [
    # ── Credentials ─────────────────────────────────────────────
    {
        "name":        "snmp_version",
        "label":       "SNMP Version",
        "type":        "text",
        "default":     "",
        "description": "Wersja SNMP dla tego urządzenia: v2c lub v3 (nadpisuje globalną konfigurację)",
        "required":    False,
        "weight":      100,
    },
    {
        "name":        "snmp_community",
        "label":       "SNMP Community (v2c)",
        "type":        "text",
        "default":     "",
        "description": "Community string SNMPv2c — nadpisuje globalny snmp_community",
        "required":    False,
        "weight":      101,
    },
    {
        "name":        "snmp_v3_username",
        "label":       "SNMP v3 Username",
        "type":        "text",
        "default":     "",
        "description": "Nazwa użytkownika SNMPv3 — nadpisuje globalny snmp_v3_username",
        "required":    False,
        "weight":      102,
    },
    {
        "name":        "snmp_v3_auth_password",
        "label":       "SNMP v3 Auth Password",
        "type":        "text",
        "default":     "",
        "description": "Hasło autoryzacji SNMPv3 (przechowywane jawnie — używaj ostrożnie)",
        "required":    False,
        "weight":      103,
    },
    {
        "name":        "snmp_v3_priv_password",
        "label":       "SNMP v3 Priv Password",
        "type":        "text",
        "default":     "",
        "description": "Hasło szyfrowania SNMPv3",
        "required":    False,
        "weight":      104,
    },
    # ── Historia odpytań ────────────────────────────────────────
    {
        "name":        "snmp_last_fetch",
        "label":       "SNMP Last Fetch",
        "type":        "text",
        "default":     "",
        "description": "Timestamp ostatniego odpytania SNMP (ISO format, ustawiany automatycznie)",
        "required":    False,
        "weight":      110,
    },
    {
        "name":        "snmp_last_fetch_by",
        "label":       "SNMP Last Fetch By",
        "type":        "text",
        "default":     "",
        "description": "Użytkownik który ostatnio odpytał urządzenie przez SNMP",
        "required":    False,
        "weight":      111,
    },
    {
        "name":        "snmp_last_fetch_status",
        "label":       "SNMP Last Fetch Status",
        "type":        "text",
        "default":     "",
        "description": "Wynik ostatniego odpytania: ok / error: <treść>",
        "required":    False,
        "weight":      112,
    },
    {
        "name":        "snmp_fetch_count",
        "label":       "SNMP Fetch Count",
        "type":        "integer",
        "default":     0,
        "description": "Liczba odpytań SNMP dla tego urządzenia",
        "required":    False,
        "weight":      113,
    },
    {
        "name":        "snmp_sys_name",
        "label":       "SNMP sysName",
        "type":        "text",
        "default":     "",
        "description": "sysName z ostatniego odpytania SNMP",
        "required":    False,
        "weight":      114,
    },
    {
        "name":        "snmp_sys_uptime",
        "label":       "SNMP Uptime",
        "type":        "text",
        "default":     "",
        "description": "Uptime z ostatniego odpytania SNMP",
        "required":    False,
        "weight":      115,
    },
    {
        "name":        "snmp_iface_summary",
        "label":       "SNMP Interface Summary",
        "type":        "text",
        "default":     "",
        "description": "Podsumowanie interfejsów: up/down/total",
        "required":    False,
        "weight":      116,
    },
]


def register_custom_fields():
    """
    Tworzy brakujące custom fields i przypisuje je do modelu dcim.device.
    Wywołane z ready() pluginu — bezpieczne przy wielokrotnym uruchomieniu.
    """
    try:
        from django.contrib.contenttypes.models import ContentType
        from extras.models import CustomField

        try:
            from dcim.models import Device
            ct = ContentType.objects.get_for_model(Device)
        except Exception as e:
            logger.warning(f"SNMP plugin: nie można pobrać ContentType dla Device: {e}")
            return

        for cf_def in CUSTOM_FIELDS:
            cf_name = cf_def["name"]
            try:
                cf, created = CustomField.objects.get_or_create(
                    name=cf_name,
                    defaults={
                        "label":       cf_def.get("label", cf_name),
                        "type":        cf_def.get("type", "text"),
                        "description": cf_def.get("description", ""),
                        "required":    cf_def.get("required", False),
                        "weight":      cf_def.get("weight", 100),
                    }
                )
                if created:
                    cf.object_types.add(ct)
                    logger.info(f"SNMP plugin: utworzono custom field '{cf_name}'")
                else:
                    # Upewnij się że pole jest przypisane do Device
                    if ct not in cf.content_types.all():
                        cf.object_types.add(ct)
            except Exception as e:
                logger.warning(f"SNMP plugin: błąd przy custom field '{cf_name}': {e}")

    except Exception as e:
        logger.warning(f"SNMP plugin: register_custom_fields failed: {e}")
