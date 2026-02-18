# main.py (device root) — AirBuddy 2.1 launcher
# Boot -> Waiting -> src/app/main.run()
#
# Board-agnostic version:
#  - Uses src.hal.board for I2C + GPS pins (Pico vs ESP32)
#  - OLED class now uses HAL by default (your patched src/ui/oled.py)

from machine import RTC
import time

from src.hal.board import init_i2c, gps_pins


# ----------------------------
# GPS pins (match src/app/main.py)
# ----------------------------
GPS_UART_ID, GPS_BAUD, GPS_TX_PIN, GPS_RX_PIN = gps_pins()


def _gc():
    try:
        import gc
        gc.collect()
    except Exception:
        pass


# ----------------------------
# OLED init
# ----------------------------
def init_oled():
    try:
        from src.ui.oled import OLED
        # OLED() will use HAL-selected I2C unless explicit pins are passed.
        return OLED()
    except Exception as e:
        print("OLED:init failed:", repr(e))
        return None


# ----------------------------
# Config
# ----------------------------
def load_cfg_dict():
    try:
        from config import load_config
        return load_config()
    except Exception as e:
        print("CONFIG error:", repr(e))
        return None


# ----------------------------
# RTC Sync
# ----------------------------
def sync_rtc_from_ds3231():
    info = {"ok": False, "synced": False, "temp_c": None}

    try:
        i2c = init_i2c()
        from src.drivers.ds3231 import DS3231
        ds = DS3231(i2c)

        year, month, day, weekday, hour, minute, sec = ds.datetime()
        wd0 = (weekday - 1) % 7
        RTC().datetime((year, month, day, wd0, hour, minute, sec, 0))

        try:
            info["temp_c"] = ds.temperature()
        except Exception:
            pass

        info["ok"] = True
        info["synced"] = True

        print("RTC synced:", (year, month, day, hour, minute, sec))
        return True, "RTC OK", info

    except Exception as e:
        print("RTC error:", repr(e))
        return False, "RTC FAIL", info


# ----------------------------
# API Device Lookup (LOW-RAM)
# ----------------------------
def api_device_lookup(cfg):
    info = {
        "ok": False,
        "device_name": "",
        "home_name": "",
        "room_name": "",
        "community_name": "",
    }

    if not cfg:
        return False, "No config", info

    device_id = (cfg.get("device_id") or "").strip()
    device_key = (cfg.get("device_key") or "").strip()
    if not device_id or not device_key:
        return False, "No device keys", info

    url = (cfg.get("api_base") or "http://air.earthen.io").rstrip("/") + "/api/v1/device?compact=1"

    r = None
    try:
        _gc()

        try:
            import ujson as json
        except Exception:
            import json

        import urequests

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
        if code != 200:
            return False, "HTTP {}".format(code if code is not None else "?"), info

        # STREAM PARSE (no r.text)
        data = json.load(r.raw)

        if not isinstance(data, dict) or not data.get("ok"):
            return False, "API not ok", info

        dev = data.get("device") or {}
        asg = data.get("assignment") or {}
        home = asg.get("home") or {}
        room = asg.get("room") or {}
        com = asg.get("community") or {}

        info["device_name"] = str(dev.get("device_name") or "")
        info["home_name"] = str(home.get("home_name") or "")
        info["room_name"] = str(room.get("room_name") or "")
        info["community_name"] = str(com.get("com_name") or "")

        info["ok"] = True
        return True, "device confirmed", info

    except MemoryError:
        return False, "ENOMEM", info

    except Exception as e:
        print("API error:", repr(e))
        return False, "API FAIL", info

    finally:
        if r:
            try:
                r.close()
            except Exception:
                pass
        _gc()


# ----------------------------
# GPS check (end of boot)
# ----------------------------
def gps_boot_check(cfg):
    """
    Lightweight GPS presence check so WaitingScreen can show GPS status.
    We do NOT keep the GPS object; src/app/main.py will init it for real.
    """
    info = {"ok": False, "enabled": False}

    try:
        enabled = bool(cfg and cfg.get("gps_enabled", False))
    except Exception:
        enabled = False

    info["enabled"] = enabled

    if not enabled:
        info["ok"] = True
        return True, "GPS off", info

    gps = None
    try:
        _gc()
        from src.app.gps_init import init_gps
        gps = init_gps(
            uart_id=GPS_UART_ID,
            baud=GPS_BAUD,
            tx_pin=GPS_TX_PIN,
            rx_pin=GPS_RX_PIN
        )
        ok = gps is not None
        info["ok"] = bool(ok)
        return bool(ok), ("GPS OK" if ok else "GPS missing"), info
    except Exception:
        info["ok"] = False
        return False, "GPS missing", info
    finally:
        try:
            gps = None
        except Exception:
            pass
        _gc()


# ----------------------------
# Waiting Screen
# ----------------------------
def go_waiting(oled, wifi_boot=None, api_boot=None, gps_boot=None):
    if oled is None:
        return
    try:
        from src.ui.waiting import WaitingScreen
        scr = WaitingScreen()
        scr.show(
            oled,
            line="Know your air...",
            animate=False,
            wifi_ok=bool(isinstance(wifi_boot, dict) and wifi_boot.get("ok")),
            gps_on=bool(isinstance(gps_boot, dict) and gps_boot.get("enabled") and gps_boot.get("ok")),
            api_ok=bool(isinstance(api_boot, dict) and api_boot.get("ok")),
        )
    except Exception as e:
        print("WAITING error:", repr(e))


# ============================================================
# BOOT SEQUENCE
# ============================================================
oled = init_oled()

cfg = None
rtc_info = None
wifi_boot = None
api_boot = None
gps_boot = None

air = None
try:
    from src.sensors.air import AirSensor
    air = AirSensor()
except Exception as e:
    print("AIR init failed:", repr(e))

try:
    from src.ui.booter import Booter
    booter = Booter(oled) if oled else None
except Exception:
    booter = None


def _log(msg):
    print(msg)


def step_load_config():
    global cfg
    cfg = load_cfg_dict()
    return (cfg is not None), ("Config OK" if cfg else "Config FAIL")


def step_rtc():
    global rtc_info
    ok, detail, info = sync_rtc_from_ds3231()
    rtc_info = info
    return ok, detail


def step_warmup():
    if air is None:
        return False, "No air sensor"
    # root boot only *starts* warmup; src/app/main.py will finish sampling later
    try:
        warmup_s = float(cfg.get("warmup_seconds", 4.0) if cfg else 4.0)
    except Exception:
        warmup_s = 4.0

    try:
        air.begin_sampling(warmup_seconds=warmup_s, source="boot")
        return True, "Warmup {:.0f}s".format(warmup_s)
    except Exception:
        return False, "Warmup err"


def step_wifi():
    global wifi_boot
    wifi_boot = {"ok": False}
    if not cfg:
        return False, "No config"

    try:
        from src.net.wifi_manager import WiFiManager
        wifi = WiFiManager()

        ok, ip, status = wifi.connect(
            cfg.get("wifi_ssid", ""),
            cfg.get("wifi_password", ""),
            timeout_s=10,
            retry=1
        )
        wifi_boot = {"ok": bool(ok), "ip": ip, "status": status}
        return bool(ok), ("WiFi is connected!" if ok else "WiFi FAIL")
    except Exception as e:
        wifi_boot = {"ok": False, "error": repr(e)}
        return False, "WiFi error"


def step_api():
    global api_boot
    if not (isinstance(wifi_boot, dict) and wifi_boot.get("ok")):
        api_boot = {"ok": False}
        return False, "No WiFi"

    ok, detail, info = api_device_lookup(cfg)
    api_boot = info
    return bool(ok), detail


def step_gps():
    global gps_boot
    ok, detail, info = gps_boot_check(cfg)
    gps_boot = info
    return bool(ok), detail


steps = [
    ("Loading config", step_load_config),
    ("RTC clock", step_rtc),
    ("Warming sensors...", step_warmup),
    ("Connecting to WiFi...", step_wifi),
    ("Device API check...", step_api),
    ("GPS check...", step_gps),
]

if booter:
    # Hold version at start for 0.5s
    # Avoid Booter’s post-finish pause (we’ll control the final message ourselves)
    booter.boot_pipeline(
        steps,
        intro_ms=500,
        fps=18,
        settle_ms=0,
        logger=_log
    )

    # Overwrite Booter’s final footer with our final message + 0.5s hold
    try:
        booter._draw_frame(p=1.0, footer="Ready to go!")
        time.sleep_ms(500)
    except Exception:
        pass
else:
    for label, fn in steps:
        _log("[BOOT] " + label)
        try:
            fn()
        except Exception as e:
            _log("ERR " + repr(e))


# Show waiting immediately after boot
go_waiting(oled, wifi_boot=wifi_boot, api_boot=api_boot, gps_boot=gps_boot)


# Launch app loop
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
