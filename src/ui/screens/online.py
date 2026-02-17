# src/ui/screens/online.py

import time
import gc
from machine import RTC

from config import load_config
from src.ui.toggle import ToggleSwitch
from src.net.telemetry_client import TelemetryClient
from src.net.wifi_manager import WiFiManager


class OnlineScreen:
    def __init__(self, oled):
        self.oled = oled
        self.wifi = WiFiManager()

        # Same vertical toggle as WiFi screen
        self.toggle = ToggleSwitch(x=100, y=6, w=24, h=52)

        self.cfg = load_config()

        self.api_base = self.cfg.get("api_base", "http://air.earthen.io")
        self.device_id = self.cfg.get("device_id", "")
        self.device_key = self.cfg.get("device_key", "")
        self.username = self.cfg.get("username", "")  # from your config.json (optional)

        self.client = TelemetryClient(
            api_base=self.api_base,
            device_id=self.device_id,
            device_key=self.device_key
        )

        # User setting: whether telemetry feature is enabled
        self._online_enabled = bool(self.cfg.get("telemetry_enabled", True))

        # UI state
        self._status = ""
        self._detail = ""
        self._connected = False  # IMPORTANT: controls toggle rendering (starts OFF)

        # Connecting animation state
        self._connecting = False
        self._dot_phase = 0
        self._next_anim_ms = 0

        # handshake scheduling (single-shot)
        self._handshake_pending = False
        self._next_handshake_ms = 0

    # ----------------------------
    # Drawing
    # ----------------------------
    def _draw(self):
        o = self.oled
        fb = o.oled
        fb.fill(0)

        title_y = 6
        o.f_arvo20.write("Online", 0, title_y)

        # "| API" in arvo16, moved DOWN 4px and LEFT 3px from previous placement
        try:
            title_w, _ = o._text_size(o.f_arvo20, "Online")
        except Exception:
            title_w = 70

        api_font = getattr(o, "f_arvo16", None) or o.f_med
        api_font.write("| API", title_w + 3, title_y + 3)  # was (title_w + 6, title_y - 1)

        # Main area
        if self._connected:
            # Connected view: 3 lines (MED, MED, SMALL)
            o.f_med.write(("user: " + (self.username or "?"))[:18], 0, 28)
            o.f_med.write(("device: " + (self.device_id or "?"))[:18], 0, 42)

            # api_base in SMALL (fallback to MED)
            try:
                o.f_small.write((self.api_base or "")[:21], 0, 54)
            except Exception:
                o.f_med.write((self.api_base or "")[:18], 0, 54)

        else:
            # Not connected view: status + detail in MED
            o.f_med.write(self._status[:18], 0, 32)
            if self._detail:
                o.f_med.write(self._detail[:18], 0, 46)

        # Toggle shows CONNECTED state, not "enabled" setting
        self.toggle.draw(fb, on=self._connected)

        fb.show()

    # ----------------------------
    # Helpers
    # ----------------------------
    def _now_unix_seconds(self):
        y, mo, d, wd, hh, mm, ss, sub = RTC().datetime()
        try:
            return int(time.mktime((y, mo, d, hh, mm, ss, wd, 0)))
        except Exception:
            return int(time.time())

    def _clean_detail(self, msg):
        s = (msg or "").strip()
        low = s.lower()
        if low.startswith("queued:"):
            s = s.split(":", 1)[1].strip()
        elif low.startswith("queued"):
            s = s[5:].strip(" :")
        return s

    # ----------------------------
    # Connecting animation (non-blocking)
    # ----------------------------
    def _set_connecting(self, on):
        self._connecting = bool(on)
        if self._connecting:
            self._dot_phase = 0
            self._next_anim_ms = time.ticks_ms()

    def _tick_connecting(self):
        if not self._connecting:
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_anim_ms) < 0:
            return

        # 0.4s per step
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
        self._next_handshake_ms = time.ticks_add(time.ticks_ms(), int(delay_ms))

    def _handshake(self):
        # Always start as NOT connected until proven otherwise
        self._connected = False
        self._detail = ""

        if not self._online_enabled:
            self._status = "Online OFF"
            self._detail = ""
            self._draw()
            return

        if not self.wifi.is_connected():
            self._status = "No WiFi"
            self._detail = ""
            self._draw()
            return

        gc.collect()
        time.sleep_ms(200)

        payload = {
            "recorded_at": self._now_unix_seconds(),
            "values": {"online_ping": 1},
            "flags": {"handshake": True},
        }

        ok, msg = self.client.send(payload)
        print("telemetry:", ok, msg)

        if ok:
            # Confirmed connection
            self._connected = True
            self._set_connecting(False)
            self._status = ""
            self._detail = ""
        else:
            # Still not connected
            self._connected = False
            self._status = "Queued"
            self._detail = self._clean_detail(msg)[:18]

        self._draw()

    # ----------------------------
    # Public
    # ----------------------------
    def show_live(self, btn):
        btn.reset()

        # Toggle should start OFF visually until we prove connectivity
        self._connected = False

        if not self._online_enabled:
            self._status = "Online OFF"
            self._detail = ""
            self._set_connecting(False)
            self._draw()
        else:
            self._set_connecting(True)
            self._status = "Connecting"
            self._detail = ""
            self._draw()
            self._request_handshake(delay_ms=600)

        while True:
            self._tick_connecting()

            action = btn.poll_action()
            if action == "single":
                return "next"

            if action == "double":
                # Toggle feature on/off (and reset connection state)
                self._online_enabled = not self._online_enabled
                self._connected = False

                if not self._online_enabled:
                    self._set_connecting(False)
                    self._handshake_pending = False
                    self._status = "Online OFF"
                    self._detail = ""
                    self._draw()
                else:
                    self._set_connecting(True)
                    self._status = "Connecting"
                    self._detail = ""
                    self._draw()
                    self._request_handshake(delay_ms=300)

            # run scheduled handshake once
            if self._online_enabled and self._handshake_pending:
                now = time.ticks_ms()
                if time.ticks_diff(now, self._next_handshake_ms) >= 0:
                    self._set_connecting(False)
                    self._handshake_pending = False
                    self._handshake()

            time.sleep_ms(25)
