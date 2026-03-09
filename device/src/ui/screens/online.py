# src/ui/screens/online.py  (MicroPython / Pico-safe)

import time
import gc
from machine import RTC

from config import load_config, save_config
from src.ui.toggle import ToggleSwitch
from src.net.telemetry_client import TelemetryClient
from src.net.wifi_manager import WiFiManager

try:
    from src.ui import connection_header as _ch
    from src.ui.connection_header import GPS_NONE
except Exception:
    _ch = None
    GPS_NONE = 0


class OnlineScreen:
    def __init__(self, oled):
        self.oled = oled
        self.wifi = WiFiManager()

        self._top_pad = 5

        # Clamp toggle to screen bounds
        w = int(getattr(oled, "width", 128))
        h = int(getattr(oled, "height", 64))

        tx = 100
        ty = 16 + self._top_pad
        tw = 24
        th = 43

        if tx + tw > w:
            tw = max(1, w - tx)
        if ty + th > h:
            th = max(1, h - ty)

        self.toggle = ToggleSwitch(x=tx, y=ty, w=tw, h=th)

        self._load_cfg()

        self.client = TelemetryClient(
            api_base=self.api_base,
            device_id=self.device_id,
            device_key=self.device_key
        )

        self._status = ""
        self._detail = ""
        self._connected = False

        self._connecting = False
        self._dot_phase = 0
        self._next_anim_ms = 0

        self._handshake_pending = False
        self._next_handshake_ms = 0

    # ----------------------------
    # Config
    # ----------------------------

    def _load_cfg(self):
        self.cfg = load_config()
        self.api_base = self.cfg.get("api_base", "http://air2.earthen.io")
        self.device_id = self.cfg.get("device_id", "")
        self.device_key = self.cfg.get("device_key", "")
        self._online_enabled = bool(self.cfg.get("telemetry_enabled", True))

    def _save_enabled(self):
        self.cfg["telemetry_enabled"] = self._online_enabled
        save_config(self.cfg)

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
                    wifi_ok=self._wifi_ok(),
                    api_connected=self._connected,
                    api_sending=False,
                    icon_y=1,
                )
            except Exception:
                pass

        title_y = self._top_pad
        o.f_arvo20.write("Online", 0, title_y)

        try:
            _, title_h = o._text_size(o.f_arvo20, "Ag")
        except Exception:
            title_h = 20

        line_h = 13
        status_y = title_y + title_h + 2

        # Status: animated dots while connecting, then API online/offline
        if self._connecting:
            status_text = self._status  # "Connecting" + dots
        elif self._connected:
            status_text = "API online"
        else:
            status_text = "API offline"
        o.f_med.write(status_text[:18], 0, status_y)

        # API base in med font
        api_str = (self.api_base or "")[:15]
        o.f_med.write(api_str, 0, status_y + line_h)

        # Masked device key in med font
        key = self.device_key or ""
        if len(key) > 5:
            key_disp = key[:5] + "*" * min(5, len(key) - 5)
        elif key:
            key_disp = key
        else:
            key_disp = "---"
        o.f_med.write("Key: " + key_disp, 0, status_y + line_h * 2)

        self.toggle.draw(fb, on=self._connected)
        fb.show()

    # ----------------------------
    # Helpers
    # ----------------------------

    def _wifi_ok(self):
        try:
            return bool(self.wifi.is_connected())
        except Exception:
            return False

    def _now_unix_seconds(self):
        y, mo, d, wd, hh, mm, ss, sub = RTC().datetime()
        try:
            return int(time.mktime((y, mo, d, hh, mm, ss, wd, 0)))
        except Exception:
            return int(time.time())

    # ----------------------------
    # Connecting animation
    # ----------------------------

    def _set_connecting(self, on):
        self._connecting = bool(on)
        if on:
            self._dot_phase = 0
            self._next_anim_ms = time.ticks_ms()

    def _tick_connecting(self):
        if not self._connecting:
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_anim_ms) < 0:
            return

        self._next_anim_ms = time.ticks_add(now, 400)
        self._dot_phase = (self._dot_phase + 1) % 4
        dots = "." * self._dot_phase
        self._status = "Connecting" + dots
        self._detail = ""
        self._draw()

    # ----------------------------
    # Handshake
    # ----------------------------

    def _request_handshake(self, delay_ms=0):
        self._handshake_pending = True
        self._next_handshake_ms = time.ticks_add(time.ticks_ms(), delay_ms)

    def _handshake(self):
        self._connected = False
        self._detail = ""

        if not self._online_enabled:
            self._status = "API OFF"
            self._draw()
            return

        if not self._wifi_ok():
            self._status = "No WiFi"
            self._draw()
            return

        gc.collect()
        time.sleep_ms(150)

        payload = {
            "recorded_at": self._now_unix_seconds(),
            "values": {"online_ping": 1},
            "flags": {"handshake": True},
        }

        ok, msg = self.client.send(payload)

        if ok:
            self._connected = True
            self._status = ""
            self._detail = ""
        else:
            self._connected = False
            self._status = "Queued"
            self._detail = str(msg or "")[:18]

        self._draw()

    # ----------------------------
    # Public
    # ----------------------------

    def show_live(self, btn, tick_fn=None):
        btn.reset()
        self._load_cfg()

        self._connected = False

        if not self._online_enabled:
            self._status = "API OFF"
            self._set_connecting(False)
            self._draw()
        else:
            self._set_connecting(True)
            self._status = "Connecting"
            self._draw()
            self._request_handshake(600)

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

            self._tick_connecting()

            try:
                action = btn.poll_action()
            except Exception:
                action = None

            if action == "single":
                return "single"   # → Logging screen

            if action == "double":
                self._online_enabled = not self._online_enabled
                self._save_enabled()
                self._connected = False
                self._handshake_pending = False
                if self._online_enabled:
                    self._set_connecting(True)
                    self._status = "Connecting"
                    self._detail = ""
                    self._draw()
                    self._request_handshake(600)
                else:
                    self._set_connecting(False)
                    self._status = "API OFF"
                    self._detail = ""
                    self._draw()
                btn.reset()

            if action == "quad":
                return "quad"

            if self._online_enabled and self._handshake_pending:
                now = time.ticks_ms()
                if time.ticks_diff(now, self._next_handshake_ms) >= 0:
                    self._handshake_pending = False
                    self._set_connecting(False)
                    self._handshake()

            time.sleep_ms(25)