# src/net/net_caps.py  (MicroPython / Pico-safe)

def wifi_supported() -> bool:
    """
    True only when a WLAN interface can be constructed.
    On non-WiFi RP2040 builds, `import network` usually fails.
    On Pico W builds it should succeed.
    """
    try:
        import network  # type: ignore
    except Exception:
        return False

    try:
        _ = network.WLAN(network.STA_IF)
        return True
    except Exception:
        return False
