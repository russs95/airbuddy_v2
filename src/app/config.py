import json
import os

CONFIG_FILE = "config.json"

DEFAULTS = {
    # --- Hardware ---
    "gps_enabled": False,

    # --- WiFi ---
    "wifi_enabled": False,
    "wifi_ssid": "Russs ",
    "wifi_password": "earthconnect",

    # --- Device Identity ---
    "device_id": "AB-0001",
    "device_key": "devkey-please-change-me",
    "username": "devuser"
}


def load_config():
    """
    Loads config from flash.
    Fills in missing keys with defaults.
    If file does not exist, creates it with defaults.
    """

    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    # Fill defaults without overwriting existing values
    changed = False
    for k, v in DEFAULTS.items():
        if k not in cfg:
            cfg[k] = v
            changed = True

    # If file was missing or incomplete, save once
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

    # Replace atomically if possible
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
