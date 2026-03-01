# config.py — AirBuddy 2.1 device configuration manager
#
# - Stores configuration in config.json on flash
# - Applies defaults
# - Normalizes types
# - Migrates legacy keys (api-base -> api_base)
# - Forces HTTP for home-first dev (avoids Pico TLS OSError(12))
# - Writes safely using temp file swap

import json
import os

CONFIG_FILE = "config.json"

# ----------------------------
# Defaults
# ----------------------------
DEFAULTS = {
    # --- Hardware ---
    "gps_enabled": True,

    # --- WiFi ---
    "wifi_enabled": True,
    "wifi_ssid": "Russs",
    "wifi_password": "earthconnect",

    # --- Telemetry ---
    "telemetry_enabled": True,
    "telemetry_post_every_s": 120,

    # --- Device Identity ---
    "api_base": "http://air.earthen.io",
    "device_id": "AB-0001",
    "device_key": "devkey-please-change-me",

    # --- Time ---
    # Minutes offset from UTC.
    # Example: Jakarta = 420
    # None means not configured (Time screen will show NO:TZ)
    "timezone_offset_min": None,
}

LEGACY_KEYS_TO_REMOVE = (
    "api-base",
)


# ----------------------------
# Public API
# ----------------------------
def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = {}

    changed = False

    # --- Migrate legacy keys ---
    if "api_base" not in cfg and "api-base" in cfg:
        cfg["api_base"] = cfg.get("api-base")
        changed = True

    for k in LEGACY_KEYS_TO_REMOVE:
        if k in cfg:
            try:
                del cfg[k]
            except Exception:
                pass
            changed = True

    # --- Apply defaults ---
    for k, v in DEFAULTS.items():
        if k not in cfg:
            cfg[k] = v
            changed = True

    # --- Normalize ---
    cfg, normalized_changed = _normalize_types(cfg)
    changed = changed or normalized_changed

    if changed or not file_exists(CONFIG_FILE):
        save_config(cfg)

    return cfg


def save_config(cfg):
    tmp_file = CONFIG_FILE + ".tmp"

    with open(tmp_file, "w") as f:
        json.dump(cfg, f)

    try:
        os.remove(CONFIG_FILE)
    except Exception:
        pass

    os.rename(tmp_file, CONFIG_FILE)


def file_exists(path):
    try:
        os.stat(path)
        return True
    except Exception:
        return False


# ----------------------------
# Normalization
# ----------------------------
def _normalize_types(cfg):
    changed = False

    # --- Booleans ---
    for key in ("gps_enabled", "wifi_enabled", "telemetry_enabled"):
        val = bool(cfg.get(key, DEFAULTS[key]))
        if cfg.get(key) is not val:
            cfg[key] = val
            changed = True

    # --- Strings ---
    wifi_ssid = str(cfg.get("wifi_ssid", "")).strip()
    wifi_password = str(cfg.get("wifi_password", "")).strip()
    api_base = str(cfg.get("api_base", "")).strip().rstrip("/")
    device_id = str(cfg.get("device_id", "")).strip()
    device_key = str(cfg.get("device_key", "")).strip()

    if api_base.startswith("https://"):
        api_base = "http://" + api_base[len("https://"):]
        changed = True

    if not api_base:
        api_base = DEFAULTS["api_base"]
        changed = True

    # --- Telemetry interval ---
    try:
        interval = int(cfg.get("telemetry_post_every_s", DEFAULTS["telemetry_post_every_s"]))
    except Exception:
        interval = DEFAULTS["telemetry_post_every_s"]
        changed = True

    if interval < 10:
        interval = 10
        changed = True

    # --- Timezone offset (minutes) ---
    tz = cfg.get("timezone_offset_min", None)

    if tz is None:
        # Not configured — valid state
        pass
    else:
        try:
            tz = int(tz)
            if -720 <= tz <= 840:  # UTC-12 to UTC+14
                if cfg.get("timezone_offset_min") != tz:
                    cfg["timezone_offset_min"] = tz
                    changed = True
            else:
                cfg["timezone_offset_min"] = None
                changed = True
        except Exception:
            cfg["timezone_offset_min"] = None
            changed = True

    # --- Write back normalized values ---
    cfg["telemetry_post_every_s"] = interval
    cfg["wifi_ssid"] = wifi_ssid
    cfg["wifi_password"] = wifi_password
    cfg["api_base"] = api_base
    cfg["device_id"] = device_id
    cfg["device_key"] = device_key

    return cfg, changed