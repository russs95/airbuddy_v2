# src/net/wifi_manager.py
# Pico W / MicroPython Wi-Fi manager (STA mode)
# Keeps things simple + robust for first bring-up.

import time

try:
    import network
except ImportError:
    network = None


class WiFiManager:
    def __init__(self):
        if network is None:
            raise RuntimeError("network module not available (are you on Pico W firmware?)")
        self.wlan = network.WLAN(network.STA_IF)
        self._last_error = ""
        self._last_status = None

    # -------------------------
    # Basic state
    # -------------------------
    def enabled(self):
        return bool(self.wlan.active())

    def active(self, on=True):
        # Turn radio on/off
        self.wlan.active(bool(on))
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
        # Returns IP string if connected, else ""
        if not self.is_connected():
            return ""
        try:
            return self.wlan.ifconfig()[0]
        except Exception:
            return ""

    def status_code(self):
        # network.WLAN.status() values vary slightly by port
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

        # Pico W / rp2 common negative codes:
        #  -1 IDLE
        #  -2 NO AP FOUND
        #  -3 WRONG PASSWORD
        #  -4 CONNECT FAIL
        if code == -1:
            return "IDLE"
        if code == -2:
            return "NO AP FOUND"
        if code == -3:
            return "WRONG PASSWORD"
        if code == -4:
            return "CONNECT FAIL"

        # Some firmwares use positive codes:
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

    def connect(self, ssid, password, timeout_s=12, retry=2):
        """
        Blocking connect attempt with timeout.
        Returns (ok:bool, ip:str, status_text:str)

        Notes:
        - Pico W often benefits from a clean disconnect before attempting connect.
        - Handles both negative (rp2) and positive status codes.
        """
        self._last_error = ""

        if not ssid:
            self._last_error = "No SSID"
            return (False, "", "NO SSID")

        self.active(True)

        # Clean slate helps avoid "half-connected" states
        try:
            self.wlan.disconnect()
        except Exception:
            pass
        time.sleep_ms(250)

        # If already connected, keep it.
        if self.is_connected():
            return (True, self.ip(), "CONNECTED")

        # Attempt connect
        try:
            self.wlan.connect(ssid, password)
        except Exception as e:
            self._last_error = "connect() threw"
            return (False, "", "CONNECT EXC")

        # Wait for connect or failure
        start = time.ticks_ms()
        last_print_ms = 0
        last_st = None

        # Early-fail codes:
        # rp2 (negative): -2 NO_AP_FOUND, -3 WRONG_PASSWORD, -4 CONNECT_FAIL
        # some firmwares (positive): 2 WRONG_PASSWORD, 3 NO_AP_FOUND, 4 CONNECT_FAIL
        early_fail = (-2, -3, -4, 2, 3, 4)

        while time.ticks_diff(time.ticks_ms(), start) < int(timeout_s * 1000):
            if self.is_connected():
                return (True, self.ip(), "CONNECTED")

            st = self.status_code()
            self._last_status = st

            # Debug: print status transitions (and at most 1/sec)
            now = time.ticks_ms()
            if (st != last_st) or (time.ticks_diff(now, last_print_ms) >= 1000):
                print("WIFI: connect st=", st, self.status_text())
                last_st = st
                last_print_ms = now

            # Early failure statuses (don’t wait full timeout)
            if st in early_fail:
                return (False, "", self.status_text())

            time.sleep_ms(200)

        # Timed out — retry with a bit more backoff
        if retry and retry > 0:
            try:
                self.wlan.disconnect()
            except Exception:
                pass

            # Increasing backoff per retry (800ms, 1300ms, 1800ms...)
            backoff_ms = 800 + (2 - retry) * 500
            time.sleep_ms(backoff_ms)

            return self.connect(ssid, password, timeout_s=timeout_s, retry=retry - 1)

        return (False, "", "TIMEOUT")

