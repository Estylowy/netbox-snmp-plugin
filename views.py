import json
import logging
from datetime import datetime, timezone
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST, require_GET
from dcim.models import Device, Interface, Site, DeviceRole
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from extras.models import Tag
from .snmp import fetch_interfaces, fetch_system_info

logger = logging.getLogger("netbox.plugins.netbox_snmp_plugin")


def _get_snmp_kwargs(device, version):
    cfg = settings.PLUGINS_CONFIG.get("netbox_snmp_plugin", {})
    port    = cfg.get("snmp_port", 161)
    timeout = cfg.get("snmp_timeout", 5)
    retries = cfg.get("snmp_retries", 2)
    common  = dict(port=port, timeout=timeout, retries=retries)
    cf = device.custom_field_data or {}
    if version == "v2c":
        community = cf.get("snmp_community") or cfg.get("snmp_community", "public")
        return dict(**common, community=community)
    return dict(
        **common,
        v3_user=       cf.get("snmp_v3_username")     or cfg.get("snmp_v3_username"),
        v3_auth_proto= cfg.get("snmp_v3_auth_protocol", "SHA"),
        v3_auth_key=   cf.get("snmp_v3_auth_password") or cfg.get("snmp_v3_auth_password"),
        v3_priv_proto= cfg.get("snmp_v3_priv_protocol", "AES"),
        v3_priv_key=   cf.get("snmp_v3_priv_password") or cfg.get("snmp_v3_priv_password"),
    )


def _update_history(device, user, status, sys_info=None, iface_summary=None):
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        cf  = device.custom_field_data or {}
        cf["snmp_last_fetch"]        = now
        cf["snmp_last_fetch_by"]     = str(user)
        cf["snmp_last_fetch_status"] = status
        cf["snmp_fetch_count"]       = int(cf.get("snmp_fetch_count") or 0) + 1
        if sys_info:
            cf["snmp_sys_name"]   = sys_info.get("sys_name", "") or ""
            cf["snmp_sys_uptime"] = sys_info.get("sys_uptime_human", "") or ""
        if iface_summary:
            cf["snmp_iface_summary"] = iface_summary
        device.custom_field_data     = cf
        device.save(update_fields=["custom_field_data"])
    except Exception as e:
        logger.warning(f"SNMP: nie można zaktualizować historii dla device {device.pk}: {e}")


def _host_from_device(device):
    if device.primary_ip:
        return str(device.primary_ip.address.ip)
    return None


@login_required
@require_POST
def snmp_interface_fetch(request, interface_id):
    iface  = get_object_or_404(Interface, pk=interface_id)
    device = iface.device
    try:
        body = json.loads(request.body)
    except Exception:
        body = {}
    version          = body.get("snmp_version", "v2c")
    include_counters = body.get("include_counters", True)
    host = _host_from_device(device)
    if not host:
        return JsonResponse({"error": "Urządzenie nie ma przypisanego Primary IP."}, status=400)
    try:
        kwargs   = _get_snmp_kwargs(device, version)
        all_snmp = fetch_interfaces(host=host, include_counters=include_counters, **kwargs)
        sys_info = fetch_system_info(host=host, **kwargs)
        status   = "ok"
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=500)
    except Exception as e:
        logger.exception(f"SNMP fetch failed for interface {interface_id}")
        _update_history(device, request.user, f"error: {e}")
        return JsonResponse({"error": f"Błąd SNMP: {str(e)}"}, status=500)
    _up   = sum(1 for s in all_snmp if s["oper_status"] == "up")
    _down = sum(1 for s in all_snmp if s["oper_status"] == "down")
    _update_history(device, request.user, status,
        sys_info=sys_info,
        iface_summary=f"\u2191{_up} \u2193{_down} /{len(all_snmp)}")
    snmp_data = None
    for s in all_snmp:
        if s["name"] == iface.name or s["description"] == iface.name:
            snmp_data = s
            break
    nb_data = {
        "id":          iface.pk,
        "name":        iface.name,
        "label":       iface.label or "",
        "description": iface.description or "",
        "enabled":     iface.enabled,
        "speed":       iface.speed,
        "mtu":         iface.mtu,
        "type":        str(iface.type) if iface.type else "",
        "mac_address": str(iface.mac_address) if iface.mac_address else "",
    }
    return JsonResponse({
        "interface_id":   interface_id,
        "interface_name": iface.name,
        "device_name":    device.name,
        "host":           host,
        "snmp_version":   version,
        "snmp":           snmp_data,
        "netbox":         nb_data,
        "system":         sys_info,
    })


@login_required
@require_POST
def snmp_interface_sync(request, interface_id):
    if not request.user.has_perm("dcim.change_interface"):
        return JsonResponse({"error": "Brak uprawnień."}, status=403)
    iface = get_object_or_404(Interface, pk=interface_id)
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Nieprawidłowy JSON."}, status=400)
    snmp    = body.get("snmp", {})
    fields  = body.get("fields", [])
    updated = []
    try:
        if "label"       in fields: iface.label       = snmp.get("label", "");       updated.append("label")
        if "description" in fields: iface.description = snmp.get("description", ""); updated.append("description")
        if "enabled"     in fields: iface.enabled      = snmp.get("oper_status") == "up"; updated.append("enabled")
        if "mtu"         in fields and snmp.get("mtu"): iface.mtu = snmp["mtu"];     updated.append("mtu")
        if "speed"       in fields and snmp.get("speed_mbps"):
            iface.speed = snmp["speed_mbps"] * 1000
            updated.append("speed")
        if "mac_address" in fields and snmp.get("mac_address"):
            iface.mac_address = snmp["mac_address"].upper()
            updated.append("mac_address")
        if "type" in fields and snmp.get("type"):
            iface.type = snmp["type"]
            updated.append("type")
        if "mac_address" in fields and snmp.get("mac_address"):
            iface.mac_address = snmp["mac_address"].upper()
            updated.append("mac_address")
        if "type" in fields and snmp.get("type"):
            iface.type = snmp["type"]
            updated.append("type")
        if updated:
            iface.save()
        return JsonResponse({"status": "ok", "updated": updated, "interface_id": iface.pk})
    except Exception as e:
        logger.exception(f"Sync error for interface {interface_id}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_GET
def snmp_bulk_page(request):
    qs = Device.objects.select_related(
        "site", "tenant", "role", "device_type",
    ).prefetch_related("tags")

    # ── Filtry ──────────────────────────────────────────────────
    site_id     = request.GET.get("site")
    role_id     = request.GET.get("role")
    status      = request.GET.get("status")
    tag_slug    = request.GET.get("tag")
    owner       = request.GET.get("owner")  # tenant
    q           = request.GET.get("q", "").strip()

    if site_id:
        qs = qs.filter(site_id=site_id)
    if role_id:
        qs = qs.filter(role_id=role_id)
    if status:
        qs = qs.filter(status=status)
    if tag_slug:
        qs = qs.filter(tags__slug=tag_slug)
    if owner:
        qs = qs.filter(tenant_id=owner)
    if q:
        qs = qs.filter(name__icontains=q)

    # ── Sortowanie ───────────────────────────────────────────────
    sort = request.GET.get("sort", "name")
    order = request.GET.get("order", "asc")
    sort_map = {
        "name":   "name",
        "site":   "site__name",
        "role":   "role__name",
        "status": "status",
        "ip":     "primary_ip4__address",
        "last_fetch": "name",  # fallback, custom field nie jest sortowalne przez ORM
    }
    sort_field = sort_map.get(sort, "name")
    if order == "desc":
        sort_field = f"-{sort_field}"
    qs = qs.order_by(sort_field)

    # ── Paginacja ────────────────────────────────────────────────
    per_page_choices = [200, 500, 1000, 2000, 3000, 5000, 10000]
    try:
        per_page = int(request.GET.get("per_page", 500))
        if per_page not in per_page_choices:
            per_page = 500
    except (ValueError, TypeError):
        per_page = 500

    paginator   = Paginator(qs, per_page)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    # ── Dane do filtrów (dropdowny) ──────────────────────────────
    sites   = Site.objects.order_by("name")
    roles   = DeviceRole.objects.order_by("name")
    tags    = Tag.objects.order_by("name")
    tenants = Device.objects.values_list(
        "tenant__id", "tenant__name"
    ).exclude(tenant=None).distinct().order_by("tenant__name")

    status_choices = [
        ("active",     "Active"),
        ("planned",    "Planned"),
        ("staged",     "Staged"),
        ("failed",     "Failed"),
        ("inventory",  "Inventory"),
        ("decommissioning", "Decommissioning"),
    ]

    return render(request, "netbox_snmp_plugin/bulk/bulk_page.html", {
        "page_obj":       page_obj,
        "paginator":      paginator,
        "per_page":       per_page,
        "per_page_choices": per_page_choices,
        "total_count":    paginator.count,
        "sites":          sites,
        "roles":          roles,
        "tags":           tags,
        "tenants":        tenants,
        "status_choices": status_choices,
        # Aktywne filtry (żeby formularze były wypełnione)
        "filter_site":    site_id or "",
        "filter_role":    role_id or "",
        "filter_status":  status or "",
        "filter_tag":     tag_slug or "",
        "filter_owner":   owner or "",
        "filter_q":       q,
        "sort":           sort,
        "order":          order,
    })


@login_required
@require_POST
def snmp_bulk_fetch(request):
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Nieprawidłowy JSON."}, status=400)
    device_ids = body.get("device_ids", [])
    version    = body.get("snmp_version", "v2c")
    if not device_ids:
        return JsonResponse({"error": "Brak device_ids."}, status=400)
    devices = Device.objects.filter(pk__in=device_ids)
    results = []
    for device in devices:
        host = _host_from_device(device)
        if not host:
            results.append({
                "device_id":   device.pk,
                "device_name": device.name,
                "status":      "error",
                "error":       "Brak Primary IP",
            })
            continue
        try:
            kwargs   = _get_snmp_kwargs(device, version)
            sys_info = fetch_system_info(host=host, **kwargs)
            ifaces   = fetch_interfaces(host=host, include_counters=False, **kwargs)
            up_count   = sum(1 for i in ifaces if i["oper_status"] == "up")
            down_count = sum(1 for i in ifaces if i["oper_status"] == "down")
            _update_history(device, request.user, "ok")
            results.append({
                "device_id":    device.pk,
                "device_name":  device.name,
                "host":         host,
                "status":       "ok",
                "system":       sys_info,
                "iface_total":  len(ifaces),
                "iface_up":     up_count,
                "iface_down":   down_count,
            })
        except Exception as e:
            _update_history(device, request.user, f"error: {e}")
            results.append({
                "device_id":   device.pk,
                "device_name": device.name,
                "host":        host,
                "status":      "error",
                "error":       str(e),
            })
    return JsonResponse({"results": results, "version": version})


@login_required
@require_GET
def snmp_device_history(request, device_id):
    device = get_object_or_404(Device, pk=device_id)
    cf     = device.custom_field_data or {}
    return JsonResponse({
        "device_id":         device_id,
        "device_name":       device.name,
        "last_fetch":        cf.get("snmp_last_fetch", ""),
        "last_fetch_by":     cf.get("snmp_last_fetch_by", ""),
        "last_fetch_status": cf.get("snmp_last_fetch_status", ""),
        "fetch_count":       cf.get("snmp_fetch_count", 0),
        "sys_name":          cf.get("snmp_sys_name", ""),
        "sys_uptime":        cf.get("snmp_sys_uptime", ""),
        "iface_summary":     cf.get("snmp_iface_summary", ""),
    })


@login_required
@require_GET
def snmp_history_by_interface(request, interface_id):
    iface  = get_object_or_404(Interface, pk=interface_id)
    device = iface.device
    cf     = device.custom_field_data or {}
    return JsonResponse({
        "interface_id":      interface_id,
        "device_name":       device.name,
        "last_fetch":        cf.get("snmp_last_fetch", ""),
        "last_fetch_by":     cf.get("snmp_last_fetch_by", ""),
        "last_fetch_status": cf.get("snmp_last_fetch_status", ""),
        "fetch_count":       cf.get("snmp_fetch_count", 0),
        "sys_name":          cf.get("snmp_sys_name", ""),
        "sys_uptime":        cf.get("snmp_sys_uptime", ""),
        "iface_summary":     cf.get("snmp_iface_summary", ""),
    })


@login_required
@require_POST
def snmp_device_fetch_interfaces(request, device_id):
    """POST /plugins/snmp/device/<id>/fetch-interfaces/"""
    device = get_object_or_404(Device, pk=device_id)
    try:
        body = json.loads(request.body)
    except Exception:
        body = {}
    version = body.get("snmp_version", "v2c")
    host = _host_from_device(device)
    if not host:
        return JsonResponse({"error": "Urządzenie nie ma przypisanego Primary IP."}, status=400)
    include_counters = body.get("include_counters", True)
    try:
        kwargs   = _get_snmp_kwargs(device, version)
        all_snmp = fetch_interfaces(host=host, include_counters=include_counters, **kwargs)
        sys_info = fetch_system_info(host=host, **kwargs)
    except Exception as e:
        logger.exception(f"SNMP device fetch failed for device {device_id}")
        _update_history(device, request.user, f"error: {e}")
        return JsonResponse({"error": f"Błąd SNMP: {str(e)}"}, status=500)

    _up   = sum(1 for s in all_snmp if s["oper_status"] == "up")
    _down = sum(1 for s in all_snmp if s["oper_status"] == "down")
    _update_history(device, request.user, "ok",
        sys_info=sys_info,
        iface_summary=f"\u2191{_up} \u2193{_down} /{len(all_snmp)}")

    # Pobierz interfejsy z NetBoxa
    nb_interfaces = {}
    for iface in Interface.objects.filter(device=device):
        nb_interfaces[iface.name] = {
            "id": iface.pk, "name": iface.name,
            "label": iface.label or "", "description": iface.description or "",
            "enabled": iface.enabled, "speed": iface.speed,
            "mtu": iface.mtu,
            "mac_address": str(iface.mac_address) if iface.mac_address else "",
            "type": str(iface.type) if iface.type else "",
        }

    merged = []
    for s in all_snmp:
        nb = nb_interfaces.get(s["name"])
        merged.append({"snmp": s, "netbox": nb})

    return JsonResponse({
        "device_id": device_id, "device_name": device.name,
        "host": host, "snmp_version": version,
        "interfaces": merged, "system": sys_info,
    })


@login_required
@require_POST
def snmp_device_sync_interfaces(request, device_id):
    """POST /plugins/snmp/device/<id>/sync-interfaces/"""
    if not request.user.has_perm("dcim.change_interface") and \
       not request.user.has_perm("dcim.add_interface"):
        return JsonResponse({"error": "Brak uprawnień."}, status=403)
    device = get_object_or_404(Device, pk=device_id)
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Nieprawidłowy JSON."}, status=400)

    items = body.get("interfaces", [])
    results = []
    for item in items:
        snmp   = item.get("snmp", {})
        action = item.get("action", "update")
        nb_id  = item.get("netbox_id")
        name   = snmp.get("name", "")
        try:
            if action == "update" and nb_id:
                iface = Interface.objects.get(pk=nb_id, device=device)
                fields = item.get("fields", ["description","label","enabled","speed","mtu","mac_address","type"])
                if "description" in fields: iface.description = snmp.get("description", "")
                if "label"       in fields: iface.label       = snmp.get("label", "")
                if "enabled"     in fields: iface.enabled     = snmp.get("oper_status") == "up"
                if "speed"       in fields and snmp.get("speed_mbps"): iface.speed = snmp["speed_mbps"] * 1000
                if "mtu"         in fields and snmp.get("mtu"):        iface.mtu   = snmp["mtu"]
                if "mac_address" in fields and snmp.get("mac_address"): iface.mac_address = snmp["mac_address"].upper()
                if "type"        in fields and snmp.get("type"):        iface.type  = snmp["type"]
                iface.save()
                results.append({"name": name, "action": "updated"})
            elif action == "create":
                if Interface.objects.filter(device=device, name=name).exists():
                    results.append({"name": name, "action": "skipped"})
                    continue
                Interface.objects.create(
                    device=device, name=name,
                    description=snmp.get("description",""),
                    label=snmp.get("label",""),
                    enabled=snmp.get("oper_status")=="up",
                    speed=snmp.get("speed_mbps",0)*1000 if snmp.get("speed_mbps") else None,
                    type="other",
                )
                results.append({"name": name, "action": "created"})
        except Exception as e:
            results.append({"name": name, "action": "error", "reason": str(e)})

    return JsonResponse({"results": results})


@login_required
@require_POST
def snmp_device_sync_device(request, device_id):
    """POST /plugins/snmp/device/<id>/sync-device/"""
    if not request.user.has_perm("dcim.change_device"):
        return JsonResponse({"error": "Brak uprawnień."}, status=403)
    device = get_object_or_404(Device, pk=device_id)
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Nieprawidłowy JSON."}, status=400)

    fields = body.get("fields", {})
    try:
        save_device = False
        for field, value in fields.items():
            if field == "name":
                device.name = value
                save_device = True
            elif field == "serial":
                device.serial = value
                save_device = True
            elif field.startswith("cf_"):
                cf_name = field[3:]
                cf = device.custom_field_data or {}
                cf[cf_name] = value
                device.custom_field_data = cf
                save_device = True

        if save_device:
            device.save()

        return JsonResponse({"status": "ok", "device_id": device_id})
    except Exception as e:
        logger.exception(f"Device sync failed for device {device_id}")
        return JsonResponse({"error": str(e)}, status=500)
