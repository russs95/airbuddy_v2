# src/app/telemetry_payload.py — Build telemetry JSON payload (Pico / MicroPython safe)
#
# Centralizes the mapping from "reading + device state" -> payload dict.
# This file is intentionally dependency-light so it can be used from scheduler/net code.
#
# Typical usage (inside your scheduler/poster code):
#   from src.app.telemetry_payload import build_payload
#   payload = build_payload(reading=reading, rtc=rtc_dict, gps=gps_fix, cfg=cfg, device=device_meta)

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


def _now_unix_s(rtc=None):
    """
    Prefer RTC unix ts if your rtc dict carries it, otherwise fall back to time.time().
    """
    # common patterns you may use later
    for k in ("unix", "unix_s", "ts", "time_s"):
        v = _get(rtc, k)
        if v is not None:
            iv = _safe_int(v, None)
            if iv is not None and iv > 1000000000:
                return iv

    try:
        return int(time.time())
    except Exception:
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
        RTC info dict from sync_system_rtc_from_ds3231(). (e.g. temp_c, synced, osf, unix, etc.)
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
    # Time
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
        # (only grabs common fields; safe if missing)
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
    # RTC info
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
        # store only safe/light fields; keep it small for Pico uploads
        meta = {}
        for k in ("serial", "model", "fw", "hw", "buwana_id", "home_id", "device_id"):
            if k in device and device.get(k) is not None:
                meta[k] = device.get(k)
        if meta:
            payload["device"] = meta

    # ----------------------------
    # Merge extra (optional)
    # ----------------------------
    if isinstance(extra, dict):
        try:
            for k, v in extra.items():
                # don't clobber core keys unless you explicitly want to
                if k not in payload:
                    payload[k] = v
        except Exception:
            pass

    return payload
