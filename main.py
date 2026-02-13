# main.py (device root) — AirBuddy 2.1 launcher + RTC sync (+ Wi-Fi bring-up)

from machine import Pin, I2C, RTC


def sync_rtc_from_ds3231():
    """
    Sync MicroPython system RTC from DS3231 (I2C0: SDA=GPIO0, SCL=GPIO1).

    Returns:
        True  -> successfully synced system time from DS3231
        False -> DS3231 missing, unreachable, or reports oscillator stop (time unreliable)
    """
    try:
        # I2C0 on Pico: SDA=GP0, SCL=GP1
        i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

        # Import here so boot still works even if driver missing
        from src.drivers.ds3231 import DS3231
        ds = DS3231(i2c)

        # If OSF is set, DS3231 time may be invalid (battery/power loss).
        # Don't overwrite system RTC with bad time.
        if ds.lost_power():
            print("RTC: DS3231 oscillator-stop flag set (time not trusted).")
            return False

        year, month, day, weekday, hour, minute, sec = ds.datetime()

        # MicroPython RTC datetime format:
        # (year, month, day, weekday, hours, minutes, seconds, subseconds)
        # DS3231 weekday is 1..7 (Mon..Sun). Convert to 0..6.
        wd0 = (weekday - 1) % 7

        RTC().datetime((year, month, day, wd0, hour, minute, sec, 0))
        print("RTC: synced from DS3231:", (year, month, day, hour, minute, sec))
        return True

    except Exception as e:
        print("RTC: sync failed:", repr(e))
        return False


def wifi_boot_connect():
    """
    Bring up Wi-Fi early (hardcoded for now) and return boot info.
    NOTE: We cannot draw OLED here because OLED is initialized inside src.app.main.
    """
    # ---- HARD CODED (temporary) ----
    WIFI_ENABLED = True
    WIFI_SSID = "Russs"
    WIFI_PASS = "earthconnect"

    info = {
        "enabled": WIFI_ENABLED,
        "ok": False,
        "ip": "",
        "status": "SKIPPED",
        "error": "",
    }

    if not WIFI_ENABLED:
        return info

    try:
        from src.net.wifi_manager import WiFiManager
        wifi = WiFiManager()

        ok, ip, status = wifi.connect(WIFI_SSID, WIFI_PASS, timeout_s=10, retry=1)

        info["ok"] = bool(ok)
        info["ip"] = ip or ""
        info["status"] = status or ("CONNECTED" if ok else "FAILED")
        info["error"] = wifi.last_error() or ""

        # Helpful boot log in REPL
        if ok:
            print("WIFI: connected:", info["ip"])
        else:
            print("WIFI: not connected:", info["status"], info["error"])

        return info

    except Exception as e:
        info["status"] = "ERROR"
        info["error"] = repr(e)
        print("WIFI: boot connect error:", info["error"])
        return info


# ---- Boot sequence ----
rtc_synced = sync_rtc_from_ds3231()
wifi_boot = wifi_boot_connect()

try:
    from src.app.main import run
    # Pass flags so app can decide what to show (e.g., Wi-Fi status screen for 4 secs)
    run(rtc_synced=rtc_synced, wifi_boot=wifi_boot)

except TypeError:
    # Backward compatibility if your run() doesn't accept args yet
    from src.app.main import run
    run()

except Exception as e:
    # Always print something helpful in REPL if boot fails
    print("AirBuddy boot error:", repr(e))
    raise
