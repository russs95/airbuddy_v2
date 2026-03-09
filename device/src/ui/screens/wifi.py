# src/ui/screens/wifi.py  (MicroPython / Pico-safe)

import time
from src.ui.toggle import ToggleSwitch
from config import load_config, save_config
from src.net.wifi_manager import WiFiManager

try:
    from src.ui import connection_header as _ch
    from src.ui.connection_header import GPS_NONE
except Exception:
    _ch = None
    GPS_NONE = 0


class WiFiScreen:
    def __init__(self, oled):
        self.oled = oled
        self.wifi = WiFiManager()

        # Move everything down by 5px (including toggle)
        self._top_pad = 5

        # Toggle: clamp to framebuffer bounds to avoid any bottom-right artifacts
        w = int(getattr(oled, "width", 128))
        h = int(getattr(oled, "height", 64))

        tx = 100
        ty = 16 + self._top_pad
        tw = 24
        th = 40

        if tx < 0:
            tx = 0
        if ty < 0:
            ty = 0

        if tx + tw > w:
            tw = max(1, w - tx)
        if ty + th > h:
            th = max(1, h - ty)

        self.toggle = ToggleSwitch(x=tx, y=ty, w=tw, h=th)

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

    def _is_connected(self):
        try:
            return bool(self.wifi.is_connected())
        except Exception:
            return False

    def _attempt_connect(self):
        """
        Attempts a single blocking connection using stored credentials.
        Updates _last_status/_last_ip and redraws once mid-try.
        """
        if not self.enabled:
            self._last_status = "Not connected"
            self._last_ip = ""
            return

        if not self.ssid:
            self._last_status = "Not connected"
            self._last_ip = ""
            return

        self._last_status = "Connecting..."
        self._last_ip = ""
        self._draw()

        ok, ip, status = self.wifi.connect(
            self.ssid,
            self.password,
            timeout_s=10,
            retry=1
        )

        if ok:
            self._last_ip = ip or ""
            self._last_status = "Connected"
        else:
            self._last_status = "Not connected"
            self._last_ip = ""

    def _live_update(self):
        """
        Queries live WiFi state and updates status text.
        """
        if self._is_connected():
            try:
                self._last_ip = self.wifi.ip() or ""
            except Exception:
                self._last_ip = ""
            self._last_status = "Connected"
        else:
            self._last_status = "Not connected"
            self._last_ip = ""

    # ----------------------------
    # Drawing
    # ----------------------------
    def _draw(self):
        o = self.oled
        fb = o.oled
        fb.fill(0)

        # Connectivity icons: top-right
        if _ch:
            try:
                _ch.draw(
                    fb,
                    o.width,
                    gps_state=GPS_NONE,
                    wifi_ok=self._is_connected(),
                    api_connected=False,
                    api_sending=False,
                    icon_y=1,
                )
            except Exception:
                pass

        # Title (moved down 5px)
        title_y = self._top_pad
        o.f_arvo20.write("WiFi", 0, title_y)

        try:
            _, title_h = o._text_size(o.f_arvo20, "Ag")
        except Exception:
            title_h = 20

        data_y = int(title_y + title_h + 4)
        line_h = 13

        connected = (self._last_status == "Connected") and self._is_connected()

        # Status line: Connecting... / Connected / Not connected
        o.f_med.write(self._last_status[:18], 0, data_y)

        if connected:
            if self.ssid:
                o.f_med.write(self.ssid[:18], 0, data_y + line_h)
            if self._last_ip:
                o.f_med.write(self._last_ip[:18], 0, data_y + line_h * 2)

        # Toggle reflects actual connection state
        self.toggle.draw(fb, on=connected)

        fb.show()

    # ----------------------------
    # Public Entry
    # ----------------------------
    def show_live(self, btn, tick_fn=None):
        """
        Single click: return "single" (connectivity carousel advances to Online screen)
        Double click: toggle WiFi enabled setting (and connect/disconnect)

        NOTE about your button.py:
        - poll_action() only emits "single"/"double" after the click window expires (default 0.8s).
          So after a single click, you won't see an action immediately; it will appear ~0.8s later.
          This loop keeps polling + sleeping so the action reliably emits.
        tick_fn: optional background callable (e.g. telemetry tick), called every 500ms.
        """
        try:
            btn.reset()
        except Exception:
            pass

        self._reload_cfg()

        # Apply stored enabled state
        if self.enabled:
            try:
                self.wifi.active(True)
            except Exception:
                pass
            self._last_status = "Connecting..."
            self._last_ip = ""
            self._draw()
            self._attempt_connect()
        else:
            try:
                self.wifi.disconnect()
            except Exception:
                pass
            try:
                self.wifi.active(False)
            except Exception:
                pass
            self._last_status = "NOT CONNECTED"
            self._last_ip = ""

        self._draw()
        self._last_refresh_ms = time.ticks_ms()
        _tick_next = time.ticks_ms()
        _tick_every = 500

        while True:
            now = time.ticks_ms()

            if tick_fn is not None and time.ticks_diff(now, _tick_next) >= 0:
                try:
                    tick_fn()
                except Exception:
                    pass
                _tick_next = time.ticks_add(now, _tick_every)

            # Periodic refresh so status updates if WiFi drops/recovers
            if time.ticks_diff(now, self._last_refresh_ms) > 500:
                self._last_refresh_ms = now
                self._live_update()
                self._draw()

            # Poll for clicks (non-blocking)
            try:
                action = btn.poll_action()
            except Exception:
                action = None

            if action == "single":
                return "single"

            elif action == "quad":
                return "quad"

            elif action == "double":
                # Toggle enabled flag + persist
                self.enabled = not self.enabled
                self.cfg["wifi_enabled"] = self.enabled
                save_config(self.cfg)

                if self.enabled:
                    try:
                        self.wifi.active(True)
                    except Exception:
                        pass
                    self._last_status = "Connecting..."
                    self._last_ip = ""
                    self._draw()
                    self._attempt_connect()
                else:
                    try:
                        self.wifi.disconnect()
                    except Exception:
                        pass
                    try:
                        self.wifi.active(False)
                    except Exception:
                        pass
                    self._last_status = "Not connected"
                    self._last_ip = ""

                self._draw()

            # Give the click-state machine time to expire its 0.8s window
            time.sleep_ms(25)