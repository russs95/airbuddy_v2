# src/ui/screens/temp.py — Temperature screen (Pico / MicroPython safe)
#
# Updated:
# - Shows AHT21 (primary) as main temp (NO calibration offset)
# - Shows AHT10 bottom-left (no "(NEW)" label)
# - Humidity bottom-right (from primary sensor reading.humidity)
# - Refresh every 4 seconds
# - Exit ONLY on single click
#
# Compatibility:
# - show_live(btn=..., air=...)            ✅ (flows.py style)
# - show_live(btn=..., get_reading=...)    ✅
# - show(reading)                         ✅ (one-shot draw)

import time
from src.ui.glyphs import draw_degree, draw_circle


class TempScreen:
    REFRESH_MS = 4000
    POLL_MS = 25

    def __init__(self, oled):
        self.oled = oled

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    @staticmethod
    def _round_1dp(x):
        try:
            return round(float(x), 1)
        except Exception:
            return None

    def _format_temp(self, t):
        if t is None:
            return None
        return "{:.1f}".format(t)

    # -------------------------------------------------
    # Drawing helpers
    # -------------------------------------------------

    def _draw_main_temp(self, temp_str, y):
        if not temp_str:
            self.oled.draw_centered(self.oled.f_large, "--.-", y)
            return

        w_num, h_large = self.oled._text_size(self.oled.f_large, temp_str)
        w_c, h_med = self.oled._text_size(self.oled.f_med, "C")

        deg_r = 2
        deg_w = deg_r * 2 + 1

        gap1 = 2
        gap2 = 2

        total_w = w_num + gap1 + deg_w + gap2 + w_c
        x0 = max(0, (self.oled.width - total_w) // 2)

        self.oled.f_large.write(temp_str, x0, y)
        x = x0 + w_num + gap1

        draw_degree(self.oled.oled, x, y + 6, r=deg_r, color=1)
        x += deg_w + gap2

        self.oled.f_med.write("C", x, y + (h_large - h_med) // 2)

    def _draw_secondary_temp(self, temp_str, x, y):
        """
        Bottom-left: ● 28.4 °C
        """
        if not temp_str:
            return

        r = 4
        cx = x + r
        cy = y + 6
        draw_circle(self.oled.oled, cx, cy, r=r, filled=True, color=1)

        x_text = x + (r * 2) + 4

        self.oled.f_med.write(temp_str, x_text, y)
        w_num, _ = self.oled._text_size(self.oled.f_med, temp_str)

        deg_r = 2
        deg_w = deg_r * 2 + 1

        x_deg = x_text + w_num + 2
        draw_degree(self.oled.oled, x_deg, y + 3, r=deg_r, color=1)

        self.oled.f_med.write("C", x_deg + deg_w + 2, y)

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------

    def show(self, reading=None):
        """
        One-shot draw (non-blocking).
        """
        self._draw_screen(reading)

    def show_live(self, btn=None, air=None, get_reading=None, refresh_ms=None):
        """
        Live refresh screen.

        Supported calling styles:
          - show_live(btn=btn, air=air)
          - show_live(btn=btn, get_reading=callable)

        Exit: single click only.
        """
        if refresh_ms is None:
            refresh_ms = self.REFRESH_MS

        # Build a getter if not provided
        if get_reading is None:
            if air is not None:
                def get_reading():
                    try:
                        fn = getattr(air, "read_quick", None)
                        if callable(fn):
                            return fn(source="temp")
                        return air.finish_sampling(log=False)
                    except Exception:
                        return None
            else:
                def get_reading():
                    return None

        next_refresh = 0
        reading = None

        while True:
            now = time.ticks_ms()

            if time.ticks_diff(now, next_refresh) >= 0:
                try:
                    reading = get_reading()
                except Exception:
                    reading = None

                self._draw_screen(reading)
                next_refresh = time.ticks_add(now, int(refresh_ms))

            action = None
            if btn is not None:
                try:
                    action = btn.poll_action()
                except Exception:
                    action = None

            if action == "single":
                return action

            time.sleep_ms(self.POLL_MS)

    # -------------------------------------------------
    # Core draw
    # -------------------------------------------------

    def _draw_screen(self, reading):
        self.oled.oled.fill(0)

        # Heading
        self.oled.draw_centered(self.oled.f_med, "Temperature", 0)

        # ---------------------------------------------
        # Primary temp (AHT21 preferred)
        # ---------------------------------------------
        temp_c = None
        if reading:
            temp_c = getattr(reading, "aht21_temp_c", None)
            if temp_c is None:
                temp_c = getattr(reading, "temp_c", None)

        if temp_c is not None:
            temp_c = self._round_1dp(temp_c)

        temp_str = self._format_temp(temp_c)

        _, h_large = self.oled._text_size(self.oled.f_large, "88.8")
        _, h_med = self.oled._text_size(self.oled.f_med, "Ag")

        y_top = h_med + 4
        y_bottom_row = self.oled.height - h_med - 1
        available = y_bottom_row - y_top
        y_val = y_top + max(0, (available - h_large) // 2)

        self._draw_main_temp(temp_str, y_val)

        # ---------------------------------------------
        # Bottom-left AHT10 temp
        # ---------------------------------------------
        sec_temp = None
        if reading:
            sec_temp = getattr(reading, "aht10_temp_c", None)

        if sec_temp is not None:
            sec_temp = self._round_1dp(sec_temp)
            sec_str = self._format_temp(sec_temp)
            self._draw_secondary_temp(sec_str, 2, y_bottom_row)

        # ---------------------------------------------
        # Bottom-right humidity (primary)
        # ---------------------------------------------
        rh = None
        if reading:
            rh = getattr(reading, "humidity", None)

        if rh is not None:
            try:
                rh_i = int(round(float(rh)))
                right_text = "RH {}%".format(rh_i)
                w, _ = self.oled._text_size(self.oled.f_med, right_text)
                x = self.oled.width - w - 2
                self.oled.f_med.write(right_text, x, y_bottom_row)
            except Exception:
                pass

        self.oled.oled.show()
