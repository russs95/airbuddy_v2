# src/ui/screens/device.py
# MicroPython / Pico-safe
#
# Device info screen
# - Device name (Arvo20 if available)
# - Left aligned data block with prefixes
# - Holds until click in show_live()

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

    # -------------------------------------------------
    # INTERNAL RENDER
    # -------------------------------------------------
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
        com = str(api_info.get("community_name") or "")

        y = 2
        x = 2  # LEFT alignment

        # ----------------------------
        # Device name (TITLE)
        # ----------------------------
        if self.f_title:
            try:
                self.f_title.write(device[:20], x, y)
                y += 22
            except Exception:
                pass

        # ----------------------------
        # Data block
        # ----------------------------
        if self.f_med:
            try:
                self.f_med.write("Home:", x, y)
                self.f_med.write(home[:16], x + 48, y)
                y += 14
            except Exception:
                pass

        if self.f_med:
            try:
                self.f_med.write("Room:", x, y)
                self.f_med.write(room[:16], x + 48, y)
                y += 14
            except Exception:
                pass

        if self.f_small:
            try:
                self.f_small.write("Community:", x, y)
                y += 10
                self.f_small.write(com[:20], x, y)
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
          btn action string ("next", "back", etc.)
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
