# src/ui/screens/device.py
# MicroPython / Pico-safe
#
# Device info screen
# - Device name (centered)
# - Left aligned data block with prefixes (values on same line)
# - Holds until click in show_live()
#
# Patch:
# - Replace Community with TZ (user timezone)
# - TZ uses MED font

import time
import gc


class DeviceScreen:

    def __init__(self, oled):
        self.oled = oled

        # Fonts (safe fallbacks)
        self.f_title = getattr(oled, "f_arvo20", None) \
                       or getattr(oled, "f_arvo16", None) \
                       or getattr(oled, "f_med", None)

        self.f_med = getattr(oled, "f_med", None) \
                     or getattr(oled, "f_small", None)

        self.f_small = getattr(oled, "f_small", None) \
                       or self.f_med

        # Layout tweak
        self.label_x = 2
        self.value_x = 48

    # -------------------------------------------------
    # INTERNAL RENDER
    # -------------------------------------------------
    def _center_x(self, writer, text, ow):
        try:
            tw, _ = writer.size(text)
            return max(0, (int(ow) - int(tw)) // 2)
        except Exception:
            return 0

    def _pick_tz(self, api_info):
        """
        Try common keys so this screen works across API shapes.
        """
        if not isinstance(api_info, dict):
            return ""

        # Most likely (your new API): api_info["time_zone"]
        tz = api_info.get("time_zone")
        if isinstance(tz, str) and tz:
            return tz

        # Sometimes nested or differently named
        for k in ("tz", "user_time_zone", "timezone"):
            tz = api_info.get(k)
            if isinstance(tz, str) and tz:
                return tz

        # If you ever pass the compact response directly, timezone may be nested
        try:
            a = api_info.get("assignment") or {}
            u = a.get("user") or {}
            tz = u.get("time_zone")
            if isinstance(tz, str) and tz:
                return tz
        except Exception:
            pass

        return ""

    def _render(self, api_info):
        if self.oled is None:
            return

        fb = getattr(self.oled, "oled", None)
        if fb is None:
            return

        fb.fill(0)

        if not isinstance(api_info, dict):
            api_info = {}

        device = str(api_info.get("device_name") or "AirBuddy")
        home = str(api_info.get("home_name") or "")
        room = str(api_info.get("room_name") or "")
        tz = self._pick_tz(api_info) or "Etc/UTC"

        ow = int(getattr(self.oled, "width", 128))

        y = 2

        # ----------------------------
        # Device name (TITLE, centered)
        # ----------------------------
        if self.f_title:
            try:
                x_title = self._center_x(self.f_title, device[:20], ow)
                self.f_title.write(device[:20], x_title, y)
                y += 22
            except Exception:
                try:
                    self.f_title.write(device[:20], 2, y)
                    y += 22
                except Exception:
                    pass

        x = int(self.label_x)
        vx = int(self.value_x)

        # ----------------------------
        # Data block (values on same line)
        # ----------------------------
        if self.f_med:
            try:
                self.f_med.write("Home:", x, y)
                self.f_med.write(home[:16], x + vx, y)
                y += 14
            except Exception:
                pass

        if self.f_med:
            try:
                self.f_med.write("Room:", x, y)
                self.f_med.write(room[:16], x + vx, y)
                y += 14
            except Exception:
                pass

        # TZ on SAME line as label (MED font)
        if self.f_med:
            try:
                self.f_med.write("TZ:", x, y)
                self.f_med.write(tz[:16], x + vx, y)
                y += 14
            except Exception:
                # fallback to small if med fails
                if self.f_small:
                    try:
                        self.f_small.write("TZ:", x, y)
                        self.f_small.write(tz[:16], x + vx, y)
                        y += 10
                    except Exception:
                        pass

        fb.show()

        try:
            gc.collect()
        except Exception:
            pass

    # -------------------------------------------------
    # SHOW (brief)
    # -------------------------------------------------
    def show(self, api_info, hold_ms=2000):
        self._render(api_info)
        if hold_ms:
            try:
                time.sleep_ms(int(hold_ms))
            except Exception:
                pass

    # -------------------------------------------------
    # SHOW LIVE (hold until click)
    # -------------------------------------------------
    def show_live(self, *, btn=None, api_info=None):
        """
        Blocks until button action.
        Returns:
          btn action string ("single", "double", "triple", etc.)
        """
        self._render(api_info)

        if btn is None:
            return None

        try:
            btn.reset()
        except Exception:
            pass

        while True:
            try:
                action = btn.poll_action()
            except Exception:
                action = None

            if action is not None:
                return action

            time.sleep_ms(25)