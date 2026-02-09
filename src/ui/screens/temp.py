# src/ui/screens/temp.py — Temperature screen (Pico / MicroPython safe)

from src.ui.glyphs import draw_degree, draw_circle


class TempScreen:
    """
    Temp screen:

      Top (MED):      "Temperature" (centered)
      Middle (LARGE): <temp>°C  (degree ring drawn in pixels + C)
      Bottom-left:    ● <rtc_temp.x>°C  (MED)  (circle glyph + 1 decimal)
      Bottom-right:   RH xx% (MED) if available
    """

    def __init__(self, oled):
        self.oled = oled

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    @staticmethod
    def _round_1dp_half_up(x):
        """
        Round to 1 decimal with half-up behavior.
        Example: 29.25 -> 29.3
        """
        try:
            x = float(x)
        except Exception:
            return None
        return int(x * 10 + 0.5) / 10.0

    # -------------------------------------------------
    # Drawing helpers
    # -------------------------------------------------
    def _draw_temp_value_large(self, temp_c, y):
        """
        Draw centered LARGE: <int temp> + degree ring + C
        """
        if temp_c is None:
            self.oled.draw_centered(self.oled.f_large, "--", y)
            return

        try:
            t = int(round(float(temp_c)))
        except Exception:
            self.oled.draw_centered(self.oled.f_large, "--", y)
            return

        num = str(t)

        # Measure widths with LARGE font
        w_num, _ = self.oled._text_size(self.oled.f_large, num)
        w_c, _ = self.oled._text_size(self.oled.f_large, "C")

        # Degree ring sizing (px)
        deg_r = 2
        deg_w = deg_r * 2 + 1  # ~5px

        total_w = w_num + 2 + deg_w + 2 + w_c
        x0 = max(0, (self.oled.width - total_w) // 2)

        # Draw number
        self.oled.f_large.write(num, x0, y)

        # Draw degree ring
        x_deg = x0 + w_num + 2
        y_deg = y + 4
        draw_degree(self.oled.oled, x_deg, y_deg, r=deg_r, color=1)

        # Draw C
        x_c = x_deg + deg_w + 2
        self.oled.f_large.write("C", x_c, y)

    def _draw_rtc_temp_left(self, rtc_temp_c, y):
        """
        Draw bottom-left: filled circle icon + <temp.x> + degree ring + C in MED.
        Temp shown with 1 decimal (half-up).
        """
        if rtc_temp_c is None:
            return

        t = self._round_1dp_half_up(rtc_temp_c)
        if t is None:
            return

        # Always show one decimal
        t_str = "{:.1f}".format(t)

        # Measure MED parts
        w_num, _ = self.oled._text_size(self.oled.f_med, t_str)
        w_c, _ = self.oled._text_size(self.oled.f_med, "C")

        deg_r = 2
        deg_w = deg_r * 2 + 1  # ~5px

        # Circle (pixel) sizing
        circ_r = 4
        circ_w = circ_r * 2 + 1  # ~9px

        # Draw starting at left padding
        x0 = 2

        # Circle baseline alignment (tuned for MED)
        cx = x0 + circ_r
        cy = y + 8
        draw_circle(self.oled.oled, cx, cy, r=circ_r, filled=True, color=1)

        x = x0 + circ_w + 2

        # Temp number (with 1 decimal)
        self.oled.f_med.write(t_str, x, y)
        x += w_num + 2

        # Degree ring (pixel)
        draw_degree(self.oled.oled, x, y + 2, r=deg_r, color=1)
        x += deg_w + 2

        # C
        self.oled.f_med.write("C", x, y)

    def _draw_rh_right(self, reading, y):
        """
        Draw bottom-right RH in MED.
        """
        rh = getattr(reading, "humidity", None) if reading is not None else None
        if rh is None:
            return
        try:
            rh_i = int(round(float(rh)))
        except Exception:
            return

        text = "RH {}%".format(rh_i)
        w, _ = self.oled._text_size(self.oled.f_med, text)
        x = max(0, self.oled.width - w - 2)
        self.oled.f_med.write(text, x, y)

    # -------------------------------------------------
    # Public
    # -------------------------------------------------
    def show(self, reading=None, rtc_temp_c=None):
        """
        reading: object with .temp_c and optionally .humidity
        rtc_temp_c: float/int temp from DS3231 (optional)
        """
        self.oled.oled.fill(0)

        # Heading
        self.oled.draw_centered(self.oled.f_med, "Temperature", 0)

        # Bottom row baseline (MED height)
        _, h_med = self.oled._text_size(self.oled.f_med, "Ag")
        y_bottom = max(0, self.oled.height - h_med - 1)

        # Value placement (LARGE)
        temp_c = getattr(reading, "temp_c", None) if reading is not None else None
        _, h_large = self.oled._text_size(self.oled.f_large, "88C")

        top_block = h_med + 2
        bottom_block = y_bottom - 1
        available = max(0, bottom_block - top_block)
        y_val = top_block + max(0, (available - h_large) // 2)

        # Main temperature
        self._draw_temp_value_large(temp_c, y_val)

        # Bottom info row (swapped)
        self._draw_rtc_temp_left(rtc_temp_c, y_bottom)
        self._draw_rh_right(reading, y_bottom)

        self.oled.oled.show()
