# config.py — AirBuddy 2.1 device configuration manager
#
# - Stores configuration in config.json on flash
# - Applies defaults
# - Normalizes types
# - Writes safely using temp file swap
# - Returns a clean dictionary ready for use

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
    "api_base": "https://air.earthen.io",
    "device_id": "AB-0001",
    "device_key": "devkey-please-change-me",
}


# ----------------------------
# Public API
# ----------------------------
def load_config():
    """
    Loads config.json from flash.
    Applies defaults and type normalization.
    Creates file if missing.
    """

    cfg = {}

    # Load existing file
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    # Apply defaults without overwriting existing values
    changed = False
    for k, v in DEFAULTS.items():
        if k not in cfg:
            cfg[k] = v
            changed = True

    # Normalize types
    cfg = _normalize_types(cfg)

    # Save if new or repaired
    if changed or not file_exists(CONFIG_FILE):
        save_config(cfg)

    return cfg


def save_config(cfg):
    """
    Safe save to flash.
    Writes to temp file first to reduce corruption risk.
    """
    tmp_file = CONFIG_FILE + ".tmp"

    with open(tmp_file, "w") as f:
        json.dump(cfg, f)

    try:
        os.remove(CONFIG_FILE)
    except Exception:
        pass

    os.rename(tmp_file, CONFIG_FILE)


# ----------------------------
# Helpers
# ----------------------------
def file_exists(path):
    try:
        os.stat(path)
        return True
    except Exception:
        return False


def _normalize_types(cfg):
    """
    Enforce correct types + strip accidental whitespace.
    Prevent subtle runtime bugs.
    """

    # Booleans
    cfg["gps_enabled"] = bool(cfg.get("gps_enabled", True))
    cfg["wifi_enabled"] = bool(cfg.get("wifi_enabled", True))
    cfg["telemetry_enabled"] = bool(cfg.get("telemetry_enabled", True))

    # Strings (strip accidental spaces)
    cfg["wifi_ssid"] = str(cfg.get("wifi_ssid", "")).strip()
    cfg["wifi_password"] = str(cfg.get("wifi_password", "")).strip()
    cfg["api_base"] = str(cfg.get("api_base", "")).strip().rstrip("/")
    cfg["device_id"] = str(cfg.get("device_id", "")).strip()
    cfg["device_key"] = str(cfg.get("device_key", "")).strip()

    # Integers
    try:
        cfg["telemetry_post_every_s"] = int(cfg.get("telemetry_post_every_s", 120))
    except Exception:
        cfg["telemetry_post_every_s"] = 120

    # Clamp to safe minimum (prevent API hammering)
    if cfg["telemetry_post_every_s"] < 10:
        cfg["telemetry_post_every_s"] = 10

    return cfg
