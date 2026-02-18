# src/hal/platform.py
# Tiny platform detection for MicroPython targets.

import sys

def platform_tag() -> str:
    # Common values:
    #  - 'rp2' for Raspberry Pi Pico / Pico W (RP2040)
    #  - 'esp32' for ESP32
    p = getattr(sys, "platform", "") or ""
    p = p.lower()

    if "rp2" in p:
        return "pico"
    if "esp32" in p:
        return "esp32"
    # Fall back: try uname
    try:
        import uos
        m = (uos.uname().machine or "").lower()
        if "rp2040" in m or "pico" in m:
            return "pico"
        if "esp32" in m:
            return "esp32"
    except Exception:
        pass

    return "unknown"
