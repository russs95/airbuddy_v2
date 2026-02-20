# src/net/wifi_manager.py
# Pico W / MicroPython Wi-Fi manager (STA mode)
# Robust connect with sane status handling across firmware variants.

import time

try:
    import network
except ImportError:
    network = None


class WiFiManager:
    supported = True

    def __init__(self):
        if network is None:
            raise RuntimeError("network module not available (are you on Pico W firmware?)")
        self.wlan = network.WLAN(network.STA_IF)
        self._last_error = ""
        self._last_status = None

        # Optional: disable power-save (often improves stability on Pico W)
        try:
            # Many rp2 builds accept this; others ignore/raise.
            self.wlan.config(pm=0xA11140)
        except Exception:
            pass

    # -------------------------
    # Basic state
    # -------------------------
    def enabled(self):
        try:
            return bool(self.wlan.active())
        except Exception:
            return False

    def active(self, on=True):
        try:
            self.wlan.active(bool(on))
        except Exception:
            return
        if not on:
            try:
                self.wlan.disconnect()
            except Exception:
                pass

    def is_connected(self):
        try:
            return bool(self.wlan.isconnected())
        except Exception:
            return False

    def ip(self):
        if not self.is_connected():
            return ""
        try:
            return self.wlan.ifconfig()[0]
        except Exception:
            return ""

    def status_code(self):
        try:
            return self.wlan.status()
        except Exception:
            return None

    def status_text(self):
        if not self.enabled():
            return "RADIO OFF"
        if self.is_connected():
            return "CONNECTED"

        code = self.status_code()

        # rp2 common codes (0..5):
        # 0 IDLE, 1 CONNECTING, 2 WRONG_PASSWORD, 3 NO_AP_FOUND, 4 CONNECT_FAIL, 5 GOT_IP
        if code == 0:
            return "IDLE"
        if code == 1:
            return "CONNECTING"
        if code == 2:
            return "WRONG PASSWORD"
        if code == 3:
            return "NO AP FOUND"
        if code == 4:
            return "CONNECT FAIL"
        if code == 5:
            return "GOT IP"

        # Some firmwares/ports return negative codes:
        # -2 NO AP FOUND, -3 WRONG PASSWORD, -4 CONNECT FAIL
        if code == -2:
            return "NO AP FOUND"
        if code == -3:
            return "WRONG PASSWORD"
        if code == -4:
            return "CONNECT FAIL"

        # IMPORTANT:
        # Some ports use -1 for CONNECT_FAIL or transient states.
        # Don't label it "IDLE" because that hides failures.
        if code == -1:
            return "UNKNOWN (-1)"

        return "DISCONNECTED"

    def last_error(self):
        return self._last_error

    # -------------------------
    # Connect / disconnect
    # -------------------------
    def disconnect(self):
        self._last_error = ""
        try:
            self.wlan.disconnect()
        except Exception:
            self._last_error = "disconnect err"
            return False
        return True

    def _hard_reset_sta(self):
        """
        Hard re-init of STA interface to clear sticky states.
        """
        try:
            self.wlan.disconnect()
        except Exception:
            pass
        try:
            self.wlan.active(False)
        except Exception:
            pass
        time.sleep_ms(200)
        try:
            self.wlan.active(True)
        except Exception:
            pass
        time.sleep_ms(250)

        # Re-apply pm config if supported
        try:
            self.wlan.config(pm=0xA11140)
        except Exception:
            pass

    def connect(self, ssid, password, timeout_s=12, retry=2):
        """
        Blocking connect attempt with timeout.
        Returns (ok:bool, ip:str, status_text:str)
        """

        self._last_error = ""

        ssid = "" if ssid is None else str(ssid)
        password = "" if password is None else str(password)

        if not ssid:
            self._last_error = "No SSID"
            return (False, "", "NO SSID")

        # If already connected, keep it.
        if self.is_connected():
            return (True, self.ip(), "CONNECTED")

        # Clean slate (more reliable than just disconnect)
        self._hard_reset_sta()

        # Attempt connect
        try:
            self.wlan.connect(ssid, password)
        except Exception:
            self._last_error = "connect() threw"
            return (False, "", "CONNECT EXC")

        start = time.ticks_ms()
        last_print_ms = 0
        last_st = None
        neg1_start = None

        # Early-fail codes:
        early_fail = (-2, -3, -4, 2, 3, 4)

        while time.ticks_diff(time.ticks_ms(), start) < int(timeout_s * 1000):
            if self.is_connected():
                return (True, self.ip(), "CONNECTED")

            st = self.status_code()
            self._last_status = st

            # Print transitions (and at most 1/sec)
            now = time.ticks_ms()
            if (st != last_st) or (time.ticks_diff(now, last_print_ms) >= 1000):
                print("WIFI: connect st=", st, self.status_text())
                last_st = st
                last_print_ms = now

            # Treat GOT_IP as success even if isconnected lags
            if st == 5:
                ip = self.ip()
                if ip:
                    return (True, ip, "CONNECTED")

            # Early failures
            if st in early_fail:
                return (False, "", self.status_text())

            # If firmware uses -1, fail if it persists (often means connect fail)
            if st == -1:
                if neg1_start is None:
                    neg1_start = now
                elif time.ticks_diff(now, neg1_start) > 1500:
                    return (False, "", self.status_text())
            else:
                neg1_start = None

            time.sleep_ms(200)

        # Timed out — retry with backoff
        if retry and retry > 0:
            try:
                self.wlan.disconnect()
            except Exception:
                pass
            backoff_ms = 800 + (2 - retry) * 500
            time.sleep_ms(backoff_ms)
            return self.connect(ssid, password, timeout_s=timeout_s, retry=retry - 1)

        return (False, "", "TIMEOUT")
