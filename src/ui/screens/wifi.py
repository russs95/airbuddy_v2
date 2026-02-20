# src/ui/screens/wifi.py

import time
from src.ui.toggle import ToggleSwitch
from config import load_config, save_config
from src.net.wifi_manager import WiFiManager


class WiFiScreen:
    def __init__(self, oled):
        self.oled = oled
        self.toggle = ToggleSwitch(x=100, y=6, w=24, h=52)

        self.wifi = WiFiManager()

        # loaded on show_live()
        self.cfg = {}
        self.enabled = False
        self.ssid = ""
        self.password = ""

        self._last_status = ""
        self._last_ip = ""
        self._last_refresh_ms = 0

    # ----------------------------
    # Helpers
    # ----------------------------
    def _reload_cfg(self):
        self.cfg = load_config()
        self.enabled = bool(self.cfg.get("wifi_enabled", False))
        self.ssid = self.cfg.get("wifi_ssid", "") or ""
        self.password = self.cfg.get("wifi_password", "") or ""

    def _masked_pw(self):
        return "********" if self.password else ""

    def _attempt_connect(self):
        """
        Attempts a single blocking connection using stored credentials.
        """
        if not self.enabled:
            self._last_status = "DISABLED"
            self._last_ip = ""
            return

        if not self.ssid:
            self._last_status = "NO SSID"
            self._last_ip = ""
            return

        self._last_status = "TRYING..."
        self._last_ip = ""
        self._draw()

        # Use explicit timeout/retry for consistent behavior
        ok, ip, status = self.wifi.connect(
            self.ssid,
            self.password,
            timeout_s=10,
            retry=1
        )

        if ok:
            self._last_ip = ip or ""
            self._last_status = "CONNECTED"
        else:
            self._last_status = status or "FAILED"
            self._last_ip = ""

    def _live_update(self):
        """
        Queries live WiFi state and updates status text.
        """
        if not self.enabled:
            self._last_status = "DISABLED"
            self._last_ip = ""
            return

        if self.wifi.is_connected():
            self._last_ip = self.wifi.ip() or ""
            self._last_status = "CONNECTED"
        else:
            self._last_status = self.wifi.status_text() or "DISCONNECTED"
            self._last_ip = ""

    # ----------------------------
    # Drawing
    # ----------------------------
    def _draw(self):
        o = self.oled
        fb = o.oled
        fb.fill(0)

        # Title
        title_writer = o.f_arvo20
        title_writer.write("WiFi", 0, 0)

        try:
            _, title_h = o._text_size(title_writer, "Ag")
        except Exception:
            title_h = 20

        data_y = int(title_h + 4)
        line_h = 14

        # Status line
        o.f_med.write(self._last_status[:18], 0, data_y)

        # If connected show info
        if self._last_status == "CONNECTED":
            o.f_small.write(self._last_ip[:18], 0, data_y + line_h)

            if self.ssid:
                o.f_small.write(self.ssid[:16], 0, data_y + line_h * 2)

            if self.password:
                pw_mask = self._masked_pw()
                try:
                    w, _ = o._text_size(o.f_small, pw_mask)
                    x = max(0, o.width - w - 2)
                except Exception:
                    x = 80
                o.f_small.write(pw_mask, x, data_y + line_h * 2)

        # Toggle
        self.toggle.draw(fb, on=self.enabled)

        fb.show()

    # ----------------------------
    # Public Entry
    # ----------------------------
    def show_live(self, btn):
        """
        Single click: go to online screen
        Double click: toggle WiFi
        """

        btn.reset()
        self._reload_cfg()

        # Apply stored enabled state
        if self.enabled:
            self.wifi.active(True)
            self._attempt_connect()
        else:
            self.wifi.active(False)
            self._last_status = "DISABLED"
            self._last_ip = ""

        self._draw()
        self._last_refresh_ms = time.ticks_ms()

        while True:
            # Periodic refresh so status updates if WiFi drops/recovers
            now = time.ticks_ms()
            if time.ticks_diff(now, self._last_refresh_ms) > 500:
                self._last_refresh_ms = now
                self._live_update()
                self._draw()

            action = btn.poll_action()


            if action == "single":
                return "next"

            if action == "double":
                self.enabled = not self.enabled
                self.cfg["wifi_enabled"] = self.enabled
                save_config(self.cfg)

                if self.enabled:
                    self.wifi.active(True)
                    self._attempt_connect()
                else:
                    self.wifi.disconnect()
                    self.wifi.active(False)
                    self._last_status = "DISABLED"
                    self._last_ip = ""

                self._draw()
