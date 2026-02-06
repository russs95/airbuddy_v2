# src/app/sysinfo.py — Pico-safe helpers

def get_time_str():
    """
    MicroPython on Pico has no real clock unless you set it (RTC or NTP).
    Return "--:--" by default.
    """
    try:
        import time
        tm = time.localtime()
        # If RTC not set, year is often 2000 or 2021-ish depending on firmware
        if tm[0] < 2024:
            return "--:--"
        return f"{tm[3]:02d}:{tm[4]:02d}"
    except Exception:
        return "--:--"


def get_ip_address():
    """
    Return IP if Wi-Fi is connected; otherwise None.
    Safe to call even if network stack isn't used.
    """
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        if not wlan.active() or not wlan.isconnected():
            return None
        return wlan.ifconfig()[0]
    except Exception:
        return None
