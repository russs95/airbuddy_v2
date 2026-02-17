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
    # Home-first dev: use HTTP (TLS can trigger ENOMEM on Pico W)
    "api_base": "http://air.earthen.io",
    "device_id": "AB-0001",
    "device_key": "devkey-please-change-me",
}

# Keys we used in older versions that we want to delete if present
LEGACY_KEYS_TO_REMOVE = (
    "api-base",          # migrated to api_base
)


# ----------------------------
# Public API
# ----------------------------
def load_config():
    """
    Loads config.json from flash.
    Applies defaults, migrations, and type normalization.
    Creates file if missing.
    """

    # Load existing file
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            cfg = {}
    except Exception:
        cfg = {}

    changed = False

    # --------- Migrate legacy keys ---------
    # If someone previously wrote "api-base", migrate it into "api_base"
    if "api_base" not in cfg and "api-base" in cfg:
        cfg["api_base"] = cfg.get("api-base")
        changed = True

    # Remove legacy keys so they don't keep reappearing
    for k in LEGACY_KEYS_TO_REMOVE:
        if k in cfg:
            try:
                del cfg[k]
            except Exception:
                pass
            changed = True

    # --------- Apply defaults (without overwriting existing values) ---------
    for k, v in DEFAULTS.items():
        if k not in cfg:
            cfg[k] = v
            changed = True

    # --------- Normalize types / values ---------
    cfg, normalized_changed = _normalize_types(cfg)
    changed = changed or normalized_changed

    # Save if new or repaired/migrated
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
    Returns: (cfg, changed_bool)
    """
    changed = False

    # Booleans
    gps_enabled = bool(cfg.get("gps_enabled", True))
    wifi_enabled = bool(cfg.get("wifi_enabled", True))
    telemetry_enabled = bool(cfg.get("telemetry_enabled", True))

    if cfg.get("gps_enabled") is not gps_enabled:
        cfg["gps_enabled"] = gps_enabled
        changed = True
    if cfg.get("wifi_enabled") is not wifi_enabled:
        cfg["wifi_enabled"] = wifi_enabled
        changed = True
    if cfg.get("telemetry_enabled") is not telemetry_enabled:
        cfg["telemetry_enabled"] = telemetry_enabled
        changed = True

    # Strings (strip accidental spaces)
    wifi_ssid = str(cfg.get("wifi_ssid", "")).strip()
    wifi_password = str(cfg.get("wifi_password", "")).strip()

    api_base = str(cfg.get("api_base", "")).strip().rstrip("/")

    device_id = str(cfg.get("device_id", "")).strip()
    device_key = str(cfg.get("device_key", "")).strip()

    if cfg.get("wifi_ssid") != wifi_ssid:
        cfg["wifi_ssid"] = wifi_ssid
        changed = True
    if cfg.get("wifi_password") != wifi_password:
        cfg["wifi_password"] = wifi_password
        changed = True

    # Force HTTP for now to avoid TLS ENOMEM on Pico W
    if api_base.startswith("https://"):
        api_base = "http://" + api_base[len("https://"):]
        changed = True

    if not api_base:
        api_base = DEFAULTS["api_base"]
        changed = True

    if cfg.get("api_base") != api_base:
        cfg["api_base"] = api_base
        changed = True

    if cfg.get("device_id") != device_id:
        cfg["device_id"] = device_id
        changed = True
    if cfg.get("device_key") != device_key:
        cfg["device_key"] = device_key
        changed = True

    # Integers
    try:
        interval = int(cfg.get("telemetry_post_every_s", DEFAULTS["telemetry_post_every_s"]))
    except Exception:
        interval = DEFAULTS["telemetry_post_every_s"]
        changed = True

    # Clamp to safe minimum (prevent API hammering)
    if interval < 10:
        interval = 10
        changed = True

    if cfg.get("telemetry_post_every_s") != interval:
        cfg["telemetry_post_every_s"] = interval
        changed = True

    return cfg, changed
