# src/ui/screens/online.py  (MicroPython / Pico-safe)

import time
import gc
from machine import RTC

from config import load_config, save_config
from src.ui.toggle import ToggleSwitch
from src.net.telemetry_client import TelemetryClient
from src.net.wifi_manager import WiFiManager


class OnlineScreen:
    def __init__(self, oled):
        self.oled = oled
        self.wifi = WiFiManager()

        self._top_pad = 5

        # Clamp toggle to screen bounds
        w = int(getattr(oled, "width", 128))
        h = int(getattr(oled, "height", 64))

        tx = 100
        ty = 6 + self._top_pad
        tw = 24
        th = 52

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
        self.api_base = self.cfg.get("api_base", "http://air.earthen.io")
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

        title_y = 6 + self._top_pad
        o.f_arvo20.write("Online", 0, title_y)

        try:
            title_w, _ = o._text_size(o.f_arvo20, "Online")
        except Exception:
            title_w = 70

        api_font = getattr(o, "f_arvo16", None) or o.f_med
        api_font.write("| API", title_w + 3, title_y + 3)

        if self._connected:
            # Removed USER line (as requested)
            o.f_med.write(("device: " + (self.device_id or "?"))[:18], 0, 32 + self._top_pad)

            try:
                o.f_small.write((self.api_base or "")[:21], 0, 48 + self._top_pad)
            except Exception:
                o.f_med.write((self.api_base or "")[:18], 0, 48 + self._top_pad)

        else:
            o.f_med.write((self._status or "")[:18], 0, 34 + self._top_pad)
            if self._detail:
                o.f_med.write((self._detail or "")[:18], 0, 48 + self._top_pad)

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

    def show_live(self, btn):
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

        while True:
            self._tick_connecting()

            try:
                action = btn.poll_action()
            except Exception:
                action = None

            if action == "single":
                return "single"   # → Logging screen

            if action == "double":
                # Double click = turn OFF API connection
                self._online_enabled = False
                self._save_enabled()
                self._connected = False
                self._set_connecting(False)
                self._handshake_pending = False
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