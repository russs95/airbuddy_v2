# src/app/sysinfo.py — Pico-safe helpers

def time_is_valid(tm, min_year=2024):
    """
    Basic sanity check: if RTC not set, year is often 2000 or 2021-ish.
    """
    try:
        return tm and tm[0] >= min_year
    except Exception:
        return False


def get_time_str():
    """
    Return "HH:MM" if system time looks valid, else "--:--"
    """
    try:
        import time
        tm = time.localtime()
        if not time_is_valid(tm):
            return "--:--"
        return f"{tm[3]:02d}:{tm[4]:02d}"
    except Exception:
        return "--:--"


def get_date_str():
    """
    Return "DD/MM/YYYY" if system time looks valid, else "--/--/----"
    """
    try:
        import time
        tm = time.localtime()
        if not time_is_valid(tm):
            return "--/--/----"
        return f"{tm[2]:02d}/{tm[1]:02d}/{tm[0]:04d}"
    except Exception:
        return "--/--/----"


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
