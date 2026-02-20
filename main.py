# main.py (device root) — AirBuddy 2.1 launcher
# Boot -> Waiting -> src/app/main.run()
#
# Board-agnostic version:
#  - Uses src.hal.board for I2C + GPS pins (Pico vs ESP32)
#  - OLED class now uses HAL by default (your patched src/ui/oled.py)
#
# Patch notes (root):
#  - Keep this file self-contained and tolerant of missing modules
#  - Use LOW-RAM device lookup client when available (src/net/device_client.py)
#  - Do NOT depend on any WaitingScreen.show_live() (root only renders once)

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


def _hex_list(addrs):
    try:
        return "[" + ", ".join("0x%02X" % a for a in addrs) + "]"
    except Exception:
        return "[]"


def i2c_scan():
    """
    One-shot I2C scan helper (safe).
    """
    try:
        i2c = init_i2c()
        return i2c.scan() or []
    except Exception:
        return []


# Common I2C addresses we care about
I2C_ADDR_OLED = 0x3C
I2C_ADDR_RTC = 0x68
I2C_ADDR_ENS160 = 0x53
I2C_ADDR_AHT2X = 0x38  # AHT20/AHT21 often


# ----------------------------
# OLED init
# ----------------------------


def init_oled():
    try:
        from src.ui.oled import OLED

        # 0 for 0.96" SSD1306
        # 2 or 4 for many 1.3" SH1106 modules
        return OLED(col_offset=2)

    except Exception as e:
        print("OLED:init failed:", repr(e))
        return None



# ----------------------------
# Config
# ----------------------------
def load_cfg_dict():
    try:
        from config import load_config
        cfg = load_config()
        return cfg if isinstance(cfg, dict) else None
    except Exception as e:
        print("CONFIG error:", repr(e))
        return None


# ----------------------------
# RTC Sync
# ----------------------------
def sync_rtc_from_ds3231():
    """
    Sync system RTC from DS3231 if detected on I2C.
    If not detected, do NOT treat as failure.
    """
    info = {"ok": False, "synced": False, "temp_c": None, "detected": False}

    try:
        addrs = i2c_scan()
        if I2C_ADDR_RTC not in addrs:
            # Not wired / not present
            info["detected"] = False
            return True, "NOT DETECTED", info

        # Detected: attempt sync
        info["detected"] = True
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
        return True, "OK", info

    except Exception as e:
        # Real error (detected but failed)
        info["ok"] = False
        info["synced"] = False
        return True, "ERROR", info  # keep boot pipeline non-fatal


# ----------------------------
# API Device Lookup (LOW-RAM)
# Prefer src/net/device_client.lookup_device_compact if present.
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
    api_base = (cfg.get("api_base") or "http://air.earthen.io").strip()

    if not device_id or not device_key:
        return False, "No device keys", info

    # --- Preferred path: your new compact client ---
    try:
        from src.net.device_client import lookup_device_compact
        ok, data, err = lookup_device_compact(api_base, device_id, device_key, timeout_s=6)
        if not ok or not isinstance(data, dict):
            return False, ("API " + str(err or "fail")), info

        info["device_name"] = str(data.get("device_name") or "")
        info["home_name"] = str(data.get("home_name") or "")
        info["room_name"] = str(data.get("room_name") or "")
        info["community_name"] = str(data.get("community_name") or "")
        info["ok"] = True
        return True, "device confirmed", info
    except Exception:
        # fall back to legacy inline implementation below
        pass

    # --- Fallback: legacy inline (kept for safety) ---
    url = api_base.rstrip("/") + "/api/v1/device?compact=1"
    r = None
    try:
        _gc()

        try:
            import ujson as json
        except Exception:
            import json  # type: ignore

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

    If enabled but no GPS data arrives, report NOT DETECTED (non-fatal).
    """
    info = {"ok": False, "enabled": False, "detected": False}

    try:
        enabled = bool(cfg and cfg.get("gps_enabled", False))
    except Exception:
        enabled = False

    info["enabled"] = enabled

    if not enabled:
        info["ok"] = True
        info["detected"] = False
        return True, "GPS off", info

    # Enabled: try init + see any bytes briefly
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
        if gps is None:
            info["ok"] = False
            info["detected"] = False
            return True, "NOT DETECTED", info

        # Probe: see if any bytes arrive
        try:
            start = time.ticks_ms()
            seen = False
            while time.ticks_diff(time.ticks_ms(), start) < 1200:
                try:
                    if gps.any():
                        b = gps.read(64) or b""
                        if b:
                            seen = True
                            break
                except Exception:
                    pass
                time.sleep_ms(50)

            info["detected"] = bool(seen)
            info["ok"] = bool(seen)
            return True, ("OK" if seen else "NOT DETECTED"), info
        except Exception:
            info["detected"] = False
            info["ok"] = False
            return True, "NOT DETECTED", info

    except Exception:
        info["ok"] = False
        info["detected"] = False
        return True, "NOT DETECTED", info
    finally:
        gps = None
        _gc()


# ----------------------------
# Waiting Screen (root renders ONCE)
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
    return True, "RTC clock -> {}".format(detail) if detail not in ("OK", "ERROR", "NOT DETECTED") else detail
    # Note: Booter prints label separately; we return just the status text.


def step_warmup():
    """
    Only warm up if ENS160/AHT appears on I2C.
    """
    if air is None:
        return True, "NO SENSORS DETECTED"

    addrs = i2c_scan()
    has_air = (I2C_ADDR_ENS160 in addrs) or (I2C_ADDR_AHT2X in addrs)

    if not has_air:
        return True, "NO SENSORS DETECTED"

    # root boot only *starts* warmup; src/app/main.py will finish sampling later
    try:
        warmup_s = float(cfg.get("warmup_seconds", 4.0) if cfg else 4.0)
    except Exception:
        warmup_s = 4.0

    try:
        air.begin_sampling(warmup_seconds=warmup_s, source="boot")
        return True, "Warmup {:.0f}s".format(warmup_s)
    except Exception:
        return True, "WARMUP ERROR"  # non-fatal


def step_wifi():
    """
    Graceful WiFi handling:
      - NOT SUPPORTED on non-WiFi boards
      - otherwise attempt connect
    """
    global wifi_boot
    wifi_boot = {"ok": False, "supported": False}

    if not cfg:
        return True, "SKIPPED (No config)"

    # Capability probe
    try:
        from src.net.net_caps import wifi_supported
        supported = bool(wifi_supported())
    except Exception:
        supported = False

    wifi_boot["supported"] = supported

    if not supported:
        return True, "NOT SUPPORTED"

    # WiFi supported: use real manager
    try:
        from src.net.wifi_manager import WiFiManager
        wifi = WiFiManager()

        ok, ip, status = wifi.connect(
            cfg.get("wifi_ssid", ""),
            cfg.get("wifi_password", ""),
            timeout_s=10,
            retry=1
        )
        wifi_boot = {"ok": bool(ok), "supported": True, "ip": ip, "status": status}
        return True, ("OK" if ok else "FAIL")
    except Exception as e:
        wifi_boot = {"ok": False, "supported": True, "error": repr(e)}
        return True, "ERROR"


def step_api():
    global api_boot

    # If no wifi or unsupported, skip cleanly
    if not (isinstance(wifi_boot, dict) and wifi_boot.get("supported") and wifi_boot.get("ok")):
        api_boot = {"ok": False}
        return True, "SKIPPED (No WiFi)"

    ok, detail, info = api_device_lookup(cfg)
    api_boot = info
    return True, ("OK" if ok else detail)


def step_gps():
    global gps_boot
    ok, detail, info = gps_boot_check(cfg)
    gps_boot = info
    return True, detail


steps = [
    ("Loading config", step_load_config),
    ("RTC clock", step_rtc),
    ("Warming sensors...", step_warmup),
    ("Connecting to WiFi...", step_wifi),
    ("Device API check...", step_api),
    ("GPS check...", step_gps),
]

if booter:
    try:
        booter.boot_pipeline(
            steps,
            intro_ms=500,
            fps=18,
            settle_ms=0,
            logger=_log
        )
    except Exception as e:
        print("BOOTER error:", repr(e))
else:
    for label, fn in steps:
        _log("[BOOT] " + label)
        try:
            ok, detail = fn()
            _log("[BOOT] {} -> {}".format(label, detail))
        except Exception as e:
            _log("[BOOT] {} -> ERROR {}".format(label, repr(e)))


# Show waiting immediately after boot (single render)
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
