# src/ui/screens/device.py
# MicroPython / Pico-safe
#
# Device info screen (on-demand)
# - show_live(...): holds until click (single -> next, double -> back after grace)
# - Layout:
#   - Device name LEFT in arvo20
#   - Data block LEFT with prefixes:
#       Home:      (MED)
#       Room:      (MED)
#       Community: (SMALL)
#
# Conventions:
#   show_live(...) -> "next" on single click (after grace)
#                 -> "back" on double click
#
# Back-compat:
#   show(api_info, hold_ms=...) exists so older callers don't crash.

import time
import gc


class DeviceScreen:
    def __init__(self, oled):
        self.oled = oled

        # Fonts (fallback chain)
        self.f_title = (
                getattr(oled, "f_arvo20", None)
                or getattr(oled, "f_arvo16", None)
                or getattr(oled, "f_med", None)
        )
        self.f_med = getattr(oled, "f_med", None) or getattr(oled, "f_small", None)
        self.f_small = getattr(oled, "f_small", None) or getattr(oled, "f_med", None)

        # Click handling
        self._single_grace_ms = 350

        # Layout
        self._pad_x = 2
        self._title_y = 2
        self._block_y = 24
        self._line_gap = 14  # MED line height-ish

    # ----------------------------
    # Safe helpers
    # ----------------------------
    def _safe_write(self, writer, text, x, y):
        if not writer or self.oled is None:
            return
        try:
            writer.write(str(text or ""), int(x), int(y))
        except Exception:
            pass

    def _clip(self, s, n=24):
        s = "" if s is None else str(s)
        return s[:n]

    # ----------------------------
    # Drawing
    # ----------------------------
    def _draw(self, api_info):
        if self.oled is None:
            return

        fb = getattr(self.oled, "oled", None)
        if fb is None:
            return

        fb.fill(0)

        info = api_info if isinstance(api_info, dict) else {}

        device = self._clip(info.get("device_name") or "AirBuddy", 22)
        home = self._clip(info.get("home_name") or "", 22)
        room = self._clip(info.get("room_name") or "", 22)
        com = self._clip(info.get("community_name") or "", 20)

        # Title (LEFT)
        self._safe_write(self.f_title, device, self._pad_x, self._title_y)

        # Block (LEFT)
        y = self._block_y
        if home:
            self._safe_write(self.f_med, "Home: " + home, self._pad_x, y)
            y += self._line_gap
        else:
            self._safe_write(self.f_med, "Home: ---", self._pad_x, y)
            y += self._line_gap

        if room:
            self._safe_write(self.f_med, "Room: " + room, self._pad_x, y)
            y += self._line_gap
        else:
            self._safe_write(self.f_med, "Room: ---", self._pad_x, y)
            y += self._line_gap

        # Community in SMALL (as requested)
        if com:
            self._safe_write(self.f_small, "Community: " + com, self._pad_x, y + 2)
        else:
            self._safe_write(self.f_small, "Community: ---", self._pad_x, y + 2)

        try:
            fb.show()
        except Exception:
            pass

        try:
            gc.collect()
        except Exception:
            pass

    # ----------------------------
    # Back-compat: timed show
    # ----------------------------
    def show(self, api_info, hold_ms=1200):
        """
        Simple timed show (for older callers).
        """
        self._draw(api_info)
        try:
            time.sleep_ms(int(hold_ms) if hold_ms else 0)
        except Exception:
            pass
        return "next"

    # ----------------------------
    # Public: hold until click
    # ----------------------------
    def show_live(self, btn, api_info):
        """
        Hold until click.
        - single click: next (after grace so double can win)
        - double click: back
        """
        # If api_info missing/invalid, still show placeholders
        info = api_info if isinstance(api_info, dict) else {}
        if not info.get("ok"):
            # still render, but placeholders will appear
            info = {
                "device_name": info.get("device_name") or "AirBuddy",
                "home_name": info.get("home_name") or "",
                "room_name": info.get("room_name") or "",
                "community_name": info.get("community_name") or "",
            }

        self._draw(info)

        if btn is None:
            return "next"

        try:
            btn.reset()
        except Exception:
            pass

        pending_single_deadline = None

        while True:
            now = time.ticks_ms()
            action = None
            try:
                action = btn.poll_action()
            except Exception:
                action = None

            # If we previously saw "single", wait briefly to see if it becomes "double"
            if pending_single_deadline is not None:
                if time.ticks_diff(now, pending_single_deadline) >= 0:
                    return "next"

            if action == "single":
                pending_single_deadline = time.ticks_add(now, self._single_grace_ms)

            elif action == "double":
                pending_single_deadline = None
                try:
                    btn.reset()
                except Exception:
                    pass
                return "back"

            time.sleep_ms(25)
