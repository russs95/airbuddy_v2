# src/app/telemetry_payload.py — Build telemetry JSON payload (Pico / MicroPython safe)
#
# Centralizes the mapping from "reading + device state" -> payload dict.
# Dependency-light so it can be used from scheduler/net code.
#
# KEY FIX (Feb 2026):
# - Do NOT trust time.time()/time.gmtime() on RP2040 ports after RTC sync.
# - Prefer deriving unix seconds from machine.RTC().datetime() using time.mktime().
# - Only fall back to rtc dict unix keys or time.time() as last resort.

import time


def _safe_int(v, default=None):
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def _safe_float(v, default=None):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _get(d, key, default=None):
    try:
        if isinstance(d, dict) and key in d:
            return d.get(key)
    except Exception:
        pass
    return default


def _safe_mktime(dt8):
    """
    MicroPython mktime signature varies slightly by port.
    We try a couple of tuple shapes.

    Expected input:
      (year, month, mday, hour, minute, second, weekday0, yearday)
    weekday0: 0..6
    """
    try:
        return int(time.mktime(dt8))
    except Exception:
        pass

    try:
        # Some ports accept: (y,mo,d,hh,mm,ss,0,0)
        y, mo, d, hh, mm, ss, wd, yd = dt8
        return int(time.mktime((int(y), int(mo), int(d), int(hh), int(mm), int(ss), 0, 0)))
    except Exception:
        return None


def _rtc_datetime_utc():
    """
    Read machine.RTC().datetime() safely.
    Returns (y,mo,d,wd0,hh,mm,ss) or None.
    """
    try:
        from machine import RTC
        dt = RTC().datetime()  # (y,mo,d,wd0,hh,mm,ss,subsec)
        if not isinstance(dt, tuple) or len(dt) < 7:
            return None
        y, mo, d, wd0, hh, mm, ss = dt[0], dt[1], dt[2], dt[3], dt[4], dt[5], dt[6]
        return (int(y), int(mo), int(d), int(wd0), int(hh), int(mm), int(ss))
    except Exception:
        return None


def _rtc_unix_s_from_machine_rtc():
    """
    Best source on RP2040 Pico builds:
      machine.RTC().datetime() -> time.mktime()
    Returns int unix seconds or None.
    """
    dt = _rtc_datetime_utc()
    if not dt:
        return None

    y, mo, d, wd0, hh, mm, ss = dt

    # Build mktime tuple:
    # (year, month, mday, hour, minute, second, weekday, yearday)
    unix_s = _safe_mktime((y, mo, d, hh, mm, ss, wd0, 0))
    if unix_s is None:
        return None

    # sanity check: epoch should be > 2001
    if int(unix_s) < 1000000000:
        return None

    return int(unix_s)


def _now_unix_s(rtc=None):
    """
    Prefer unix seconds derived from machine.RTC().datetime().
    Fall back to rtc dict unix keys if present.
    Finally fall back to time.time().
    """
    # 1) Best: machine RTC -> mktime
    u = _rtc_unix_s_from_machine_rtc()
    if u is not None:
        return u

    # 2) If caller passed a live rtc dict carrying unix seconds
    for k in ("unix", "unix_s", "ts", "time_s"):
        v = _get(rtc, k)
        if v is not None:
            iv = _safe_int(v, None)
            if iv is not None and iv > 1000000000:
                return iv

    # 3) Last resort: time.time()
    try:
        t = int(time.time())
        if t > 1000000000:
            return t
    except Exception:
        pass

    return None


def build_payload(reading=None, rtc=None, gps=None, cfg=None, device=None, extra=None):
    """
    Build a dict that can be JSON-encoded.

    Parameters
    ----------
    reading : dict|object|None
        Expected to contain e.g. eco2_ppm, tvoc_ppb, temp_c, rh, aqi, etc.
        If it's an object, we'll try attribute access as a fallback.
    rtc : dict|None
        RTC info dict from boot sync (temp_c, synced, osf, etc.). May be a snapshot.
    gps : dict|None
        Optional GPS fix dict (lat, lon, alt_m, sats, hdop, fix, etc.)
    cfg : dict|None
        Optional config snapshot (telemetry_enabled, interval, etc.)
    device : dict|None
        Optional device metadata (serial, model, fw, hw, buwana_id, home_id, etc.)
    extra : dict|None
        Any additional fields you want to merge in.

    Returns
    -------
    dict
    """
    payload = {}

    # ----------------------------
    # Time (UTC unix seconds)
    # ----------------------------
    payload["ts"] = _now_unix_s(rtc=rtc)

    # ----------------------------
    # Reading (dict or object)
    # ----------------------------
    r = {}
    if isinstance(reading, dict):
        r = reading
    elif reading is not None:
        # attribute fallback for sensor classes that return objects
        r = {
            "eco2_ppm": getattr(reading, "eco2_ppm", None),
            "tvoc_ppb": getattr(reading, "tvoc_ppb", None),
            "temp_c": getattr(reading, "temp_c", None),
            "rh": getattr(reading, "rh", None),
            "aqi": getattr(reading, "aqi", None),
            "confidence": getattr(reading, "confidence", None),
        }

    payload["air"] = {
        "eco2_ppm": _safe_int(_get(r, "eco2_ppm"), None),
        "tvoc_ppb": _safe_int(_get(r, "tvoc_ppb"), None),
        "temp_c": _safe_float(_get(r, "temp_c"), None),
        "rh": _safe_float(_get(r, "rh"), None),
        "aqi": _safe_int(_get(r, "aqi"), None),
        "confidence": _safe_int(_get(r, "confidence"), None),
    }

    # ----------------------------
    # RTC info (snapshot)
    # ----------------------------
    payload["rtc"] = {
        "synced": bool(_get(rtc, "synced", False)),
        "osf": bool(_get(rtc, "osf", False)),
        "temp_c": _safe_float(_get(rtc, "temp_c"), None),
    }

    # ----------------------------
    # GPS (optional)
    # ----------------------------
    if isinstance(gps, dict):
        payload["gps"] = {
            "fix": _safe_int(_get(gps, "fix"), None),
            "lat": _safe_float(_get(gps, "lat"), None),
            "lon": _safe_float(_get(gps, "lon"), None),
            "alt_m": _safe_float(_get(gps, "alt_m"), None),
            "sats": _safe_int(_get(gps, "sats"), None),
            "hdop": _safe_float(_get(gps, "hdop"), None),
        }

    # ----------------------------
    # Config snapshot (optional)
    # ----------------------------
    if isinstance(cfg, dict):
        payload["cfg"] = {
            "telemetry_enabled": bool(cfg.get("telemetry_enabled", True)),
            "telemetry_post_every_s": _safe_int(cfg.get("telemetry_post_every_s"), None),
            "gps_enabled": bool(cfg.get("gps_enabled", True)),
        }

    # ----------------------------
    # Device meta (optional)
    # ----------------------------
    if isinstance(device, dict):
        meta = {}
        for k in ("serial", "model", "fw", "hw", "buwana_id", "home_id", "device_id"):
            try:
                if k in device and device.get(k) is not None:
                    meta[k] = device.get(k)
            except Exception:
                pass
        if meta:
            payload["device"] = meta

    # ----------------------------
    # Merge extra (optional)
    # ----------------------------
    if isinstance(extra, dict):
        try:
            for k, v in extra.items():
                if k not in payload:
                    payload[k] = v
        except Exception:
            pass

    return payload