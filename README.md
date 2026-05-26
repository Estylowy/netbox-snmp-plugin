# netbox_snmp_plugin

NetBox 4.x plugin for querying devices and interfaces via SNMP, comparing data with NetBox, and synchronizing changes.

---

## Features

### Device detail page
- **SNMP Device** button — fetches system info: sysName, sysDescr, Uptime, sysContact, sysLocation, OS version, Serial
- Field-by-field comparison with NetBox data
- Sync selected fields to NetBox custom fields
- **SNMP Inspector** panel in the right column: last poll, user, status, sysName, uptime, interfaces ↑/↓/total

### Interfaces tab and interface detail page
- **SNMP** button — modal with tabs:
  - **Interfaces** — full SNMP vs NetBox interface table with per-interface expand and sync for: description, label, status, speed, MTU, MAC, type
  - **Counters** — 64-bit counter totals (in/out octets, unicast, errors, discards)
  - **History** — last poll, user, status, sysName, uptime
- **Demo** button — sample data without a live device connection
- **Counters** toggle — enable/disable counter fetching
- SNMP **v2c / v3** selector
- Interface filtering, "differences only" view, "select all"
- Draggable and resizable modal

### Bulk page (SNMP Inspector → Poll devices)
- All devices with filtering by Site, Role, Status, Owner, Tag, name
- Pagination: 200 / 500 / 1000 / 2000 / 3000 / 5000 / 10000 per page
- Column sorting
- Results: sysName, uptime, interfaces ↑/↓/total

---

## Requirements

- NetBox **4.x** (tested on 4.5.4)
- Python **3.12+**
- `easysnmp` (not pysnmp)
- System libraries: `net-snmp`, `net-snmp-devel`
- Primary IP set on the device in NetBox
- **NetBox server IP allowed in SNMP ACL on devices** (UDP 161)

---

## Installation

### 1. System libraries

```bash
sudo dnf install net-snmp net-snmp-devel python3-devel gcc -y
```

### 2. Download and install

Clone or download this repository. The folder structure must be preserved exactly as follows — pip requires it to install correctly:

```
netbox_snmp_plugin/
├── setup.py
├── MANIFEST.in
└── netbox_snmp_plugin/
    ├── __init__.py
    ├── views.py
    ├── urls.py
    ├── snmp.py
    ├── navigation.py
    ├── custom_fields.py
    ├── template_content.py
    ├── migrations/
    ├── templates/
    └── templatetags/
```

If you're uploading manually (e.g. via GitHub download), make sure to recreate this folder structure on your server before installing.

```bash
sudo /opt/netbox/venv/bin/pip install easysnmp
sudo /opt/netbox/venv/bin/pip install /opt/plugins/netbox_snmp_plugin/
```

### 3. Add to configuration.py

```python
PLUGINS = [
    "netbox_snmp_plugin",
]

PLUGINS_CONFIG = {
    "netbox_snmp_plugin": {
        "snmp_community":        "your_community",
        "snmp_v3_username":      "your_username",
        "snmp_v3_auth_protocol": "SHA",
        "snmp_v3_auth_password": "your_auth_password",
        "snmp_v3_priv_protocol": "AES",
        "snmp_v3_priv_password": "your_priv_password",
        "snmp_port":    161,
        "snmp_timeout": 5,
        "snmp_retries": 2,
    },
}
```

### 4. Migrate and restart

```bash
sudo /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate
sudo /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq
```

### 5. Test SNMP connectivity

```bash
# SNMPv2c
snmpwalk -v 2c -c <community> <device_ip> sysName

# SNMPv3
snmpwalk -v3 -l authPriv -u <user> -a SHA -A <auth_pass> -x AES -X <priv_pass> <device_ip> sysName
```

---

## Custom fields (auto-created on Device)

| Field | Description |
|-------|-------------|
| `snmp_community` | SNMPv2c community string (per-device override) |
| `snmp_v3_username` | SNMPv3 username (per-device override) |
| `snmp_v3_auth_password` | SNMPv3 auth password |
| `snmp_v3_priv_password` | SNMPv3 priv password |
| `snmp_last_fetch` | Timestamp of last poll |
| `snmp_last_fetch_by` | User who triggered the poll |
| `snmp_last_fetch_status` | ok / error: ... |
| `snmp_fetch_count` | Poll counter |
| `snmp_sys_name` | sysName |
| `snmp_sys_uptime` | Uptime |
| `snmp_iface_summary` | ↑up ↓down /total |
| `snmp_sys_descr` | sysDescr |
| `snmp_sys_contact` | sysContact |
| `snmp_sys_location` | sysLocation |
| `os` | OS version (parsed from sysDescr) |

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/plugins/snmp/device/<id>/fetch-interfaces/` | Fetch SNMP data for a device |
| POST | `/plugins/snmp/device/<id>/sync-interfaces/` | Sync interfaces to NetBox |
| POST | `/plugins/snmp/device/<id>/sync-device/` | Sync device fields to NetBox |
| GET  | `/plugins/snmp/device/<id>/history/` | Poll history |
| GET  | `/plugins/snmp/bulk/` | Bulk page |
| POST | `/plugins/snmp/bulk/fetch/` | Bulk fetch |
