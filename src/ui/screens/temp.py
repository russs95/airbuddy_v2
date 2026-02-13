# src/ui/screens/temp.py — Temperature screen (Pico / MicroPython safe)

from src.ui.glyphs import draw_degree, draw_circle


class TempScreen:
    """
    Clean temperature screen:

      Top (MED):      "Temperature" (centered)
      Middle (LARGE): 31.7 °C  (degree glyph + MED C)
      Bottom-left:    ● 28.4 °C (RTC temp, filled circle glyph)
      Bottom-right:   RH xx%
    """

    CALIBRATION_OFFSET = -3.0  # subtract 3°C from measured value

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
        """
        Draw centered LARGE number + pixel degree + MED C.
        """

        if not temp_str:
            self.oled.draw_centered(self.oled.f_large, "--.-", y)
            return

        # Measure pieces
        w_num, h_large = self.oled._text_size(self.oled.f_large, temp_str)
        w_c, h_med = self.oled._text_size(self.oled.f_med, "C")

        deg_r = 2
        deg_w = deg_r * 2 + 1

        gap1 = 2  # number -> degree
        gap2 = 2  # degree -> C

        total_w = w_num + gap1 + deg_w + gap2 + w_c
        x0 = max(0, (self.oled.width - total_w) // 2)

        # Draw LARGE number
        self.oled.f_large.write(temp_str, x0, y)
        x = x0 + w_num + gap1

        # Draw pixel degree
        draw_degree(self.oled.oled, x, y + 6, r=deg_r, color=1)
        x += deg_w + gap2

        # Draw MED "C"
        self.oled.f_med.write("C", x, y + (h_large - h_med) // 2)

    def _draw_rtc_temp(self, rtc_str, x, y):
        """
        Draw: ● 28.4 °C  (MED text + pixel degree)
        """

        if not rtc_str:
            return

        # Draw filled circle glyph (reliable)
        r = 4
        cx = x + r
        cy = y + 6
        draw_circle(self.oled.oled, cx, cy, r=r, filled=True, color=1)

        x_text = x + (r * 2) + 4

        # Draw temp number
        self.oled.f_med.write(rtc_str, x_text, y)
        w_num, h_med = self.oled._text_size(self.oled.f_med, rtc_str)

        deg_r = 2
        deg_w = deg_r * 2 + 1

        x_deg = x_text + w_num + 2
        draw_degree(self.oled.oled, x_deg, y + 3, r=deg_r, color=1)

        self.oled.f_med.write("C", x_deg + deg_w + 2, y)

    # -------------------------------------------------
    # Public
    # -------------------------------------------------

    def show(self, reading=None, rtc_temp_c=None):
        self.oled.oled.fill(0)

        # -------------------------------------------------
        # Heading
        # -------------------------------------------------
        self.oled.draw_centered(self.oled.f_med, "Temperature", 0)

        # -------------------------------------------------
        # Main sensor temp (apply calibration)
        # -------------------------------------------------
        temp_c = getattr(reading, "temp_c", None) if reading else None

        if temp_c is not None:
            temp_c = self._round_1dp(temp_c + self.CALIBRATION_OFFSET)

        temp_str = self._format_temp(temp_c)

        # Layout calculations
        _, h_large = self.oled._text_size(self.oled.f_large, "88.8")
        _, h_med = self.oled._text_size(self.oled.f_med, "Ag")

        y_top = h_med + 4
        y_bottom_row = self.oled.height - h_med - 1

        available = y_bottom_row - y_top
        y_val = y_top + max(0, (available - h_large) // 2)

        # Draw main temperature
        self._draw_main_temp(temp_str, y_val)

        # -------------------------------------------------
        # Bottom-left RTC temp (no calibration)
        # -------------------------------------------------
        rtc_str = None
        if rtc_temp_c is not None:
            rtc_temp_c = self._round_1dp(rtc_temp_c)
            rtc_str = self._format_temp(rtc_temp_c)

        self._draw_rtc_temp(rtc_str, 2, y_bottom_row)

        # -------------------------------------------------
        # Bottom-right humidity
        # -------------------------------------------------
        rh = getattr(reading, "humidity", None) if reading else None
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
