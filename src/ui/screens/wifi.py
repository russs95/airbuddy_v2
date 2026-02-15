# src/ui/screens/wifi.py

import time
from src.ui.toggle import ToggleSwitch
from src.app.config import load_config, save_config
from src.net.wifi_manager import WiFiManager


class WiFiScreen:
    def __init__(self, oled):
        self.oled = oled
        self.toggle = ToggleSwitch(x=100, y=6, w=24, h=52)

        self.wifi = WiFiManager()
        self.cfg = load_config()

        self.enabled = bool(self.cfg.get("wifi_enabled", False))
        self.ssid = self.cfg.get("wifi_ssid", "")
        self.password = self.cfg.get("wifi_password", "")

        self._last_status = ""
        self._last_ip = ""

    # ----------------------------
    # Helpers
    # ----------------------------
    def _masked_pw(self):
        return "********" if self.password else ""

    def _attempt_connect(self):
        """
        Attempts a single blocking connection using stored credentials.
        """
        if not self.ssid:
            self._last_status = "NO SSID"
            return

        self._last_status = "TRYING..."
        self._draw()

        ok, ip, status = self.wifi.connect(self.ssid, self.password)

        if ok:
            self._last_ip = ip
            self._last_status = "CONNECTED"
        else:
            self._last_status = status
            self._last_ip = ""

    def _live_update(self):
        """
        Queries live WiFi state.
        """
        if not self.enabled:
            self._last_status = "DISABLED"
            self._last_ip = ""
            return

        if self.wifi.is_connected():
            self._last_ip = self.wifi.ip()
            self._last_status = "CONNECTED"
        else:
            self._last_status = self.wifi.status_text()
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

        # Apply stored enabled state
        if self.enabled:
            self.wifi.active(True)
            # Auto-test connection if already enabled
            self._attempt_connect()
        else:
            self.wifi.active(False)
            self._last_status = "DISABLED"

        self._draw()

        while True:
            action = btn.wait_for_action()

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
