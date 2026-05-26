import logging
from typing import Optional

logger = logging.getLogger("netbox.plugins.netbox_snmp_plugin")

OID_ifDescr        = ".1.3.6.1.2.1.2.2.1.2"
OID_ifName         = ".1.3.6.1.2.1.31.1.1.1.1"
OID_ifAlias        = ".1.3.6.1.2.1.31.1.1.1.18"
OID_ifOperStatus   = ".1.3.6.1.2.1.2.2.1.8"
OID_ifAdminStatus  = ".1.3.6.1.2.1.2.2.1.7"
OID_ifHighSpeed    = ".1.3.6.1.2.1.31.1.1.1.15"
OID_ifSpeed        = ".1.3.6.1.2.1.2.2.1.5"
OID_ifMtu          = ".1.3.6.1.2.1.2.2.1.4"
OID_ifPhysAddress  = ".1.3.6.1.2.1.2.2.1.6"
OID_ifInOctets     = ".1.3.6.1.2.1.2.2.1.10"
OID_ifOutOctets    = ".1.3.6.1.2.1.2.2.1.16"
OID_ifInUcastPkts  = ".1.3.6.1.2.1.2.2.1.11"
OID_ifOutUcastPkts = ".1.3.6.1.2.1.2.2.1.17"
OID_ifInErrors     = ".1.3.6.1.2.1.2.2.1.14"
OID_ifOutErrors    = ".1.3.6.1.2.1.2.2.1.20"
OID_ifInDiscards   = ".1.3.6.1.2.1.2.2.1.13"
OID_ifOutDiscards  = ".1.3.6.1.2.1.2.2.1.19"
OID_ifHCInOctets   = ".1.3.6.1.2.1.31.1.1.1.6"
OID_ifHCOutOctets  = ".1.3.6.1.2.1.31.1.1.1.10"
OID_ifHCInUcast    = ".1.3.6.1.2.1.31.1.1.1.7"
OID_ifHCOutUcast   = ".1.3.6.1.2.1.31.1.1.1.11"
OID_sysDescr       = ".1.3.6.1.2.1.1.1.0"
OID_sysName        = ".1.3.6.1.2.1.1.5.0"
OID_sysUpTime      = ".1.3.6.1.2.1.1.3.0"
OID_sysContact     = ".1.3.6.1.2.1.1.4.0"
OID_sysLocation    = ".1.3.6.1.2.1.1.6.0"

OPER_STATUS  = {1:"up", 2:"down", 3:"testing", 4:"unknown",
                5:"dormant", 6:"notPresent", 7:"lowerLayerDown"}
ADMIN_STATUS = {1:"up", 2:"down", 3:"testing"}


def _make_session(host, port, timeout, retries, community=None,
                  v3_user=None, v3_auth_proto=None, v3_auth_key=None,
                  v3_priv_proto=None, v3_priv_key=None):
    try:
        from easysnmp import Session
    except ImportError:
        raise RuntimeError("Brak biblioteki easysnmp. Zainstaluj: pip install easysnmp")

    if community:
        return Session(
            hostname=host,
            remote_port=port,
            community=community,
            version=2,
            timeout=timeout,
            retries=retries,
        )
    else:
        auth_map = {"SHA": "SHA", "MD5": "MD5"}
        priv_map = {"AES": "AES", "DES": "DES"}
        return Session(
            hostname=host,
            remote_port=port,
            version=3,
            security_username=v3_user,
            security_level="auth_with_privacy",
            auth_protocol=auth_map.get((v3_auth_proto or "SHA").upper(), "SHA"),
            auth_password=v3_auth_key,
            privacy_protocol=priv_map.get((v3_priv_proto or "AES").upper(), "AES"),
            privacy_password=v3_priv_key,
            timeout=timeout,
            retries=retries,
        )


def _walk(session, oid):
    result = {}
    try:
        items = session.walk(oid)
        for item in items:
            idx = str(item.oid_index)
            try:
                result[idx] = int(item.value)
            except (ValueError, TypeError):
                result[idx] = str(item.value)
    except Exception as e:
        logger.warning(f"SNMP walk error OID {oid}: {e}")
    return result


def _get_scalar(session, oid):
    try:
        item = session.get(oid)
        return str(item.value)
    except Exception as e:
        logger.warning(f"SNMP get error OID {oid}: {e}")
        return None


def fetch_system_info(host, port=161, timeout=5, retries=2,
                      community=None, v3_user=None, v3_auth_proto=None,
                      v3_auth_key=None, v3_priv_proto=None, v3_priv_key=None):
    session = _make_session(host, port, timeout, retries, community,
                            v3_user, v3_auth_proto, v3_auth_key,
                            v3_priv_proto, v3_priv_key)
    result = {
        "sys_name":     _get_scalar(session, OID_sysName),
        "sys_descr":    _get_scalar(session, OID_sysDescr),
        "sys_uptime":   _get_scalar(session, OID_sysUpTime),
        "sys_contact":  _get_scalar(session, OID_sysContact),
        "sys_location": _get_scalar(session, OID_sysLocation),
    }
    if result.get("sys_uptime"):
        try:
            cs = int(result["sys_uptime"])
            total_s = cs // 100
            days  = total_s // 86400
            hours = (total_s % 86400) // 3600
            mins  = (total_s % 3600) // 60
            result["sys_uptime_human"] = f"{days}d {hours}h {mins}m"
        except Exception:
            result["sys_uptime_human"] = result["sys_uptime"]
    return result


def fetch_interfaces(host, port=161, timeout=5, retries=2,
                     community=None, v3_user=None, v3_auth_proto=None,
                     v3_auth_key=None, v3_priv_proto=None, v3_priv_key=None,
                     include_counters=False):
    session = _make_session(host, port, timeout, retries, community,
                            v3_user, v3_auth_proto, v3_auth_key,
                            v3_priv_proto, v3_priv_key)
    data = {
        "name":      _walk(session, OID_ifName),
        "descr":     _walk(session, OID_ifDescr),
        "alias":     _walk(session, OID_ifAlias),
        "oper":      _walk(session, OID_ifOperStatus),
        "admin":     _walk(session, OID_ifAdminStatus),
        "highspeed": _walk(session, OID_ifHighSpeed),
        "speed":     _walk(session, OID_ifSpeed),
        "mtu":       _walk(session, OID_ifMtu),
    }
    if include_counters:
        data.update({
            "hc_in_oct":    _walk(session, OID_ifHCInOctets),
            "hc_out_oct":   _walk(session, OID_ifHCOutOctets),
            "hc_in_ucast":  _walk(session, OID_ifHCInUcast),
            "hc_out_ucast": _walk(session, OID_ifHCOutUcast),
            "in_oct":       _walk(session, OID_ifInOctets),
            "out_oct":      _walk(session, OID_ifOutOctets),
            "in_ucast":     _walk(session, OID_ifInUcastPkts),
            "out_ucast":    _walk(session, OID_ifOutUcastPkts),
            "in_err":       _walk(session, OID_ifInErrors),
            "out_err":      _walk(session, OID_ifOutErrors),
            "in_disc":      _walk(session, OID_ifInDiscards),
            "out_disc":     _walk(session, OID_ifOutDiscards),
        })

    all_indices = set(data["name"].keys()) | set(data["descr"].keys())
    interfaces = []
    for idx in sorted(all_indices, key=lambda x: int(x) if x.isdigit() else 0):
        name  = data["name"].get(idx) or data["descr"].get(idx) or f"if{idx}"
        descr = data["descr"].get(idx, "")
        alias = data["alias"].get(idx, "")
        oper_raw  = data["oper"].get(idx, 0)
        admin_raw = data["admin"].get(idx, 0)
        high_speed = data["highspeed"].get(idx, 0)
        if_speed   = data["speed"].get(idx, 0)
        speed_mbps = int(high_speed) if high_speed else (int(if_speed) // 1_000_000 if if_speed else 0)
        mtu = data["mtu"].get(idx)
        # Określ typ interfejsu na podstawie prędkości
        if speed_mbps >= 100000:
            iface_type = "100gbase-x-qsfp28"
        elif speed_mbps >= 40000:
            iface_type = "40gbase-x-qsfpp"
        elif speed_mbps >= 25000:
            iface_type = "25gbase-x-sfp28"
        elif speed_mbps >= 10000:
            iface_type = "10gbase-x-sfpp"
        elif speed_mbps >= 1000:
            iface_type = "1000base-t"
        elif speed_mbps >= 100:
            iface_type = "100base-tx"
        elif speed_mbps > 0:
            iface_type = "other"
        else:
            iface_type = "other"

        mac_str = ""

        entry = {
            "index":        idx,
            "name":         str(name),
            "description":  str(descr),
            "label":        str(alias),
            "oper_status":  OPER_STATUS.get(int(oper_raw) if oper_raw else 0, "unknown"),
            "admin_status": ADMIN_STATUS.get(int(admin_raw) if admin_raw else 0, "unknown"),
            "speed_mbps":   speed_mbps,
            "mtu":          int(mtu) if mtu else None,
            "mac_address":  mac_str,
            "type":         iface_type,
        }
        if include_counters:
            entry["counters"] = {
                "in_octets":    data["hc_in_oct"].get(idx)    or data["in_oct"].get(idx, 0),
                "out_octets":   data["hc_out_oct"].get(idx)   or data["out_oct"].get(idx, 0),
                "in_ucast":     data["hc_in_ucast"].get(idx)  or data["in_ucast"].get(idx, 0),
                "out_ucast":    data["hc_out_ucast"].get(idx) or data["out_ucast"].get(idx, 0),
                "in_errors":    data["in_err"].get(idx, 0),
                "out_errors":   data["out_err"].get(idx, 0),
                "in_discards":  data["in_disc"].get(idx, 0),
                "out_discards": data["out_disc"].get(idx, 0),
            }
        interfaces.append(entry)
    return interfaces
