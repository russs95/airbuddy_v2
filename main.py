# main.py (device root) — AirBuddy 2.1 launcher + step-boot pipeline
# - RTC sync (once)
# - load config
# - start sensor warmup (non-blocking)
# - connect Wi-Fi
# - device lookup: GET https://air.earthen.io/api/v1/device
# - show assignment for 4s
# - launch src/app/main.run(...)

from machine import Pin, I2C, RTC
import time


# ----------------------------
# OLED init (root-level)
# ----------------------------
def init_oled():
    try:
        from src.ui.oled import OLED
        return OLED()
    except Exception as e:
        print("OLED:init failed:", repr(e))
        return None


# ----------------------------
# Config Loader (dict-based)
# ----------------------------
def load_cfg_dict():
    try:
        from config import load_config
        return load_config()
    except Exception as e:
        print("CONFIG: missing/invalid config.py:", repr(e))
        return None


# ----------------------------
# RTC Sync (returns rtc_info dict)
# ----------------------------
def sync_rtc_from_ds3231():
    info = {
        "ok": False,
        "synced": False,
        "osf": None,
        "temp_c": None,
        "dt": None,
        "ticking": None,
        "sane": None,
    }

    try:
        i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
        from src.drivers.ds3231 import DS3231
        ds = DS3231(i2c)

        osf = False
        try:
            osf = bool(ds.lost_power())
        except Exception:
            osf = None

        info["osf"] = osf

        year, month, day, weekday, hour, minute, sec = ds.datetime()
        wd0 = (weekday - 1) % 7
        RTC().datetime((year, month, day, wd0, hour, minute, sec, 0))

        info["dt"] = (year, month, day, wd0, hour, minute, sec)

        # temp if driver supports it
        try:
            info["temp_c"] = ds.temperature()
        except Exception:
            info["temp_c"] = None

        info["synced"] = (osf is False) or (osf is None)
        info["ok"] = True

        print("RTC: synced from DS3231:", (year, month, day, hour, minute, sec))
        return True, "RTC OK", info

    except Exception as e:
        print("RTC: sync failed:", repr(e))
        info["ok"] = False
        info["synced"] = False
        return False, "RTC FAIL", info


# ----------------------------
# Sensor warmup (start only)
# ----------------------------
def start_sensor_warmup(cfg, air_sensor):
    try:
        warmup_s = float(cfg.get("warmup_seconds", 4.0) if cfg else 4.0)
    except Exception:
        warmup_s = 4.0

    try:
        air_sensor.begin_sampling(warmup_seconds=warmup_s, source="boot")
        return True, "Warmup {:.0f}s".format(warmup_s)
    except Exception as e:
        return False, "Warmup err"


# ----------------------------
# Wi-Fi Boot Connect
# ----------------------------
def wifi_boot_connect(cfg):
    info = {
        "enabled": False,
        "ok": False,
        "ip": "",
        "status": "SKIPPED",
        "error": "",
    }

    if cfg is None:
        info["status"] = "NO_CONFIG"
        return False, "No config", info

    WIFI_ENABLED = bool(cfg.get("wifi_enabled", True))
    WIFI_SSID = (cfg.get("wifi_ssid", "") or "").strip()
    WIFI_PASS = (cfg.get("wifi_password", "") or "").strip()

    info["enabled"] = WIFI_ENABLED

    if not WIFI_ENABLED:
        info["status"] = "DISABLED"
        return True, "WiFi disabled", info

    if not WIFI_SSID or not WIFI_PASS:
        info["status"] = "MISSING_CREDS"
        info["error"] = "wifi_ssid/wifi_password not set"
        print("WIFI: missing credentials in config.json")
        return False, "WiFi creds missing", info

    try:
        from src.net.wifi_manager import WiFiManager
        wifi = WiFiManager()

        ok, ip, status = wifi.connect(WIFI_SSID, WIFI_PASS, timeout_s=10, retry=1)

        info["ok"] = bool(ok)
        info["ip"] = ip or ""
        info["status"] = status or ("CONNECTED" if ok else "FAILED")
        info["error"] = wifi.last_error() or ""

        if ok:
            print("WIFI: connected:", info["ip"])
            return True, "WiFi connected", info
        else:
            print("WIFI: not connected:", info["status"], info["error"])
            return False, "WiFi fail", info

    except Exception as e:
        info["status"] = "ERROR"
        info["error"] = repr(e)
        print("WIFI: boot connect error:", info["error"])
        return False, "WiFi error", info


# ----------------------------
# API: device lookup (OMEM-safe)
# ----------------------------
def api_boot_device_lookup(cfg, wifi_info):
    info = {
        "ok": False,
        "status": "SKIPPED",
        "error": "",
        "device_name": "",
        "home_name": "",
        "room_name": "",
        "community_name": "",
    }

    if not isinstance(wifi_info, dict) or not wifi_info.get("ok"):
        info["status"] = "NO_WIFI"
        return False, "No WiFi", info

    if cfg is None:
        info["status"] = "NO_CONFIG"
        return False, "No config", info

    device_id = (cfg.get("device_id", "") or "").strip()
    device_key = (cfg.get("device_key", "") or "").strip()

    if not device_id or not device_key:
        info["status"] = "NO_DEVICE_KEYS"
        info["error"] = "device_id/device_key missing"
        return False, "No device keys", info

    url = "https://air.earthen.io/api/v1/device?compact=1"

    try:
        import gc
        import ujson
        import urequests
        gc.collect()

        headers = {
            "X-Device-Id": device_id,
            "X-Device-Key": device_key,
            "Accept": "application/json",
            "Connection": "close",
        }

        try:
            r = urequests.get(url, headers=headers, timeout=6)
        except TypeError:
            r = urequests.get(url, headers=headers)

        code = getattr(r, "status_code", None)
        info["status"] = str(code) if code is not None else "NO_STATUS"

        try:
            text = r.text
        except Exception:
            text = None

        try:
            r.close()
        except Exception:
            pass

        del r
        gc.collect()

        if not text:
            info["ok"] = False
            info["status"] = "NO_BODY"
            info["error"] = "empty response"
            return False, "API empty", info

        try:
            data = ujson.loads(text)
        except Exception as e:
            info["ok"] = False
            info["status"] = "BAD_JSON"
            info["error"] = "json parse: " + repr(e)
            return False, "API bad json", info
        finally:
            del text
            gc.collect()

        ok = bool(isinstance(data, dict) and data.get("ok"))
        info["ok"] = ok

        if not ok:
            info["error"] = "not-ok"
            return False, "API fail", info

        dev = data.get("device") or {}
        asg = data.get("assignment") or {}
        home = asg.get("home") or {}
        room = asg.get("room") or {}
        com = asg.get("community") or {}

        info["device_name"] = str(dev.get("device_name") or "").strip()
        info["home_name"] = str(home.get("home_name") or "").strip()
        info["room_name"] = str(room.get("room_name") or "").strip()
        info["community_name"] = str(com.get("com_name") or "").strip()

        del data
        gc.collect()

        return True, "API OK", info

    except Exception as e:
        info["status"] = "ERROR"
        info["error"] = repr(e)
        print("API: lookup error:", info["error"])
        return False, "API error", info


# ----------------------------
# Assignment splash screen (4s)
# ----------------------------
def show_assignment(oled, api_info, ms=4000):
    if oled is None:
        return
    if not isinstance(api_info, dict) or not api_info.get("ok"):
        return

    fb = oled.oled
    fb.fill(0)

    f = getattr(oled, "f_med", None) or getattr(oled, "f_arvo16", None) or getattr(oled, "f_small", None)
    if not f:
        return

    # Four lines max on 64px height (med is usually 12-14px tall)
    device = api_info.get("device_name") or "AirBuddy"
    home = api_info.get("home_name") or ""
    room = api_info.get("room_name") or ""
    com = api_info.get("community_name") or ""

    lines = [
        device,
        (home + (" / " + room if room else "")).strip(" /"),
        com,
        "Locked & loaded!",
    ]

    y = 2
    for s in lines:
        s = str(s)
        if len(s) > 20:
            s = s[:20]
        try:
            oled.draw_centered(f, s, y)
        except Exception:
            f.write(s, 0, y)
        y += 15

    fb.show()
    time.sleep_ms(int(ms))


# ----------------------------
# Root boot sequence using Booter pipeline
# ----------------------------
oled = init_oled()

cfg = None
rtc_info = None
wifi_boot = None
api_boot = None

air = None
try:
    from src.sensors.air import AirSensor
    air = AirSensor()
except Exception as e:
    print("AIR: init failed:", repr(e))
    air = None

try:
    from src.ui.booter import Booter
    booter = Booter(oled) if oled else None
except Exception as e:
    print("BOOTER:init failed:", repr(e))
    booter = None

def _log(msg):
    print(msg)

# Build pipeline steps (label, fn)
steps = []

def step_load_config():
    global cfg
    cfg = load_cfg_dict()
    return (cfg is not None), ("Config OK" if cfg is not None else "Config FAIL")

def step_rtc():
    global rtc_info
    ok, detail, info = sync_rtc_from_ds3231()
    rtc_info = info
    return ok, detail

def step_warmup():
    if air is None:
        return False, "No air sensor"
    return start_sensor_warmup(cfg, air)

def step_wifi():
    global wifi_boot
    ok, detail, info = wifi_boot_connect(cfg)
    wifi_boot = info
    return ok, detail

def step_api():
    global api_boot
    ok, detail, info = api_boot_device_lookup(cfg, wifi_boot or {})
    api_boot = info
    return ok, detail

steps = [
    ("Loading config", step_load_config),
    ("RTC clock", step_rtc),
    ("Warming sensors", step_warmup),
    ("Connecting to WiFi", step_wifi),
    ("Checking device", step_api),
]

# Run pipeline with visual progress + mpremote logs
if booter:
    booter.boot_pipeline(steps, intro_ms=500, fps=18, settle_ms=120, logger=_log)
else:
    # fallback: just run steps
    for label, fn in steps:
        _log("[BOOT] " + label)
        try:
            fn()
        except Exception as e:
            _log("[BOOT] EXC " + label + ": " + repr(e))

# Optional: show assignment for 4s if API OK
show_assignment(oled, api_boot, ms=4000)

# Launch app core loop
try:
    from src.app.main import run
    run(
        rtc_synced=bool(rtc_info and rtc_info.get("synced")),
        wifi_boot=wifi_boot,
        api_boot=api_boot,
        oled=oled,
        air_sensor=air,
        boot_warmup_started=True,
        rtc_info=rtc_info
    )
except Exception as e:
    print("AirBuddy boot error:", repr(e))
    raise
