import json

CONFIG_FILE = "config.json"

DEFAULTS = {
    "gps_enabled": False,
    "wifi_enabled": False,
}

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
    except:
        cfg = {}

    # fill defaults
    for k, v in DEFAULTS.items():
        if k not in cfg:
            cfg[k] = v

    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f)
