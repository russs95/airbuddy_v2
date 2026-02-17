# src/ui/screens/time.py — Time + RTC info screen (Pico / MicroPython safe)

import time
from src.ui.glyphs import draw_circle, draw_degree


class TimeScreen:
    MONTHS = (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    )

    def __init__(self, oled):
        self.oled = oled

        # Colon tweak:
        # We hide the font ":" and draw our own colon, OFFSET from the font position.
        # Positive values move the colon DOWN.
        self.COLON_OFFSET_PX = 3  # ✅ lower by 6px

    # ----------------------------
    # Formatting
    # ----------------------------
    def _suffix(self, day):
        if 11 <= (day % 100) <= 13:
            return "th"
        last = day % 10
        return "st" if last == 1 else "nd" if last == 2 else "rd" if last == 3 else "th"

    def _pretty_date(self, date_str):
        try:
            if not date_str or date_str.startswith("--"):
                return "--"
            parts = date_str.split("/")
            if len(parts) != 3:
                return date_str
            d = int(parts[0]); m = int(parts[1]); y = int(parts[2])
            if not (1 <= m <= 12 and 1 <= d <= 31):
                return date_str
            return "{} {}{}, {}".format(self.MONTHS[m - 1], d, self._suffix(d), y)
        except Exception:
            return date_str

    def _blink_time(self, time_str, blink_on=True):
        # Turn ":" into " " when blink is off
        if not time_str or time_str.startswith("--"):
            return time_str
        if ":" in time_str:
            return time_str if blink_on else time_str.replace(":", " ", 1)
        return time_str

    # ----------------------------
    # Drawing blocks
    # ----------------------------
    def _draw_bottom_left_source(self, source, y):
        source = (source or "SYS").upper()
        filled = (source == "RTC")
        label = "RTC" if filled else "SYS"

        cx = 9
        cy = y + 5
        r = 4
        draw_circle(self.oled.oled, cx, cy, r=r, filled=filled, color=1)
        self.oled.f_med.write(label, 18, y)

    def _draw_bottom_right_temp(self, temp_c, y):
        """
        Draw: 25.3°C in MED, 1 decimal
        Degree ring is pixel glyph; C is font.
        """
        if temp_c is None:
            return
        try:
            t = round(float(temp_c), 1)
        except Exception:
            return

        t_text = "{:.1f}".format(t)
        w_t, _ = self.oled._text_size(self.oled.f_med, t_text)
        w_c, _ = self.oled._text_size(self.oled.f_med, "C")

        deg_r = 2
        deg_w = deg_r * 2 + 1
        total_w = w_t + 1 + deg_w + 1 + w_c

        x0 = max(0, self.oled.width - total_w - 2)

        self.oled.f_med.write(t_text, x0, y)

        x_deg = x0 + w_t + 1
        y_deg = y + 2
        draw_degree(self.oled.oled, x_deg, y_deg, r=deg_r, color=1)

        x_c = x_deg + deg_w + 1
        self.oled.f_med.write("C", x_c, y)

    # ----------------------------
    # Colon override
    # ----------------------------
    def _find_colon_x(self, time_str, y_time):
        """
        Compute x position of the first ":" in the centered LARGE time string.
        Returns (colon_x, colon_w, text_x0) or (None, None, None).
        """
        if not time_str or ":" not in time_str:
            return None, None, None

        # Measure using the LARGE font used for the main time.
        w_full, _ = self.oled._text_size(self.oled.f_large, time_str)
        x0 = max(0, (self.oled.width - int(w_full)) // 2)

        idx = time_str.find(":")
        left = time_str[:idx]
        w_left, _ = self.oled._text_size(self.oled.f_large, left)

        w_colon, _ = self.oled._text_size(self.oled.f_large, ":")

        colon_x = x0 + int(w_left)
        return int(colon_x), int(w_colon), int(x0)

    def _draw_colon_override(self, time_str, y_time):
        """
        Hide the font's colon (by blanking its area), then draw a 2-dot colon with an offset.
        Positive offset moves DOWN.
        """
        if not time_str or ":" not in time_str:
            return

        colon_x, colon_w, _ = self._find_colon_x(time_str, y_time)
        if colon_x is None:
            return

        if colon_w <= 0:
            colon_w = 6

        _, h_large = self.oled._text_size(self.oled.f_large, "88:88")
        self.oled.oled.fill_rect(colon_x, y_time, colon_w, int(h_large), 0)

        mid_y = y_time + int(h_large // 2)
        dot_x = colon_x + max(0, (colon_w // 2) - 1)

        offset_px = int(self.COLON_OFFSET_PX)

        # Two 2x2 dots
        self.oled.oled.fill_rect(dot_x, mid_y - 8 + offset_px, 2, 2, 1)
        self.oled.oled.fill_rect(dot_x, mid_y + 2 + offset_px, 2, 2, 1)

    # ----------------------------
    # Render
    # ----------------------------
    def _render(self, date_str, time_str, source="SYS", temp_c=None, blink_on=True):
        self.oled.oled.fill(0)

        # --- Top: pretty date (MED) ---
        pretty = self._pretty_date(date_str)
        _, h_med = self.oled._text_size(self.oled.f_med, pretty)
        self.oled.draw_centered(self.oled.f_med, pretty, 0)

        # --- Bottom row layout (MED height) ---
        _, h_bottom = self.oled._text_size(self.oled.f_med, "Ag")
        y_bottom = max(0, self.oled.height - h_bottom - 1)

        # --- Center: time (LARGE, with blinking colon) ---
        t_disp = self._blink_time(time_str, blink_on=blink_on)

        # Compute vertical placement for LARGE time
        _, h_large = self.oled._text_size(self.oled.f_large, "88:88")
        top_block = h_med + 2
        bottom_block = y_bottom - 1
        available = max(0, bottom_block - top_block)
        y_time = top_block + max(0, (available - h_large) // 2)

        # Draw LARGE time (hours/minutes) using oled.f_large
        self.oled.draw_centered(self.oled.f_large, t_disp, y_time)

        # If blink is ON, we want ":" visible — but overridden.
        if blink_on and time_str and (":" in time_str):
            self._draw_colon_override(time_str, y_time)

        # --- Bottom-left/source + bottom-right/temp ---
        self._draw_bottom_left_source(source, y_bottom)
        self._draw_bottom_right_temp(temp_c, y_bottom)

        self.oled.oled.show()

    # ----------------------------
    # Public: static show
    # ----------------------------
    def show(self, date_str, time_str, source="SYS", temp_c=None):
        self._render(date_str, time_str, source=source, temp_c=temp_c, blink_on=True)

    # ----------------------------
    # Public: live show with blink + exit on click
    # ----------------------------
    def show_live(
            self,
            get_date_str,
            get_time_str,
            get_source,
            get_temp_c,
            btn=None,
            max_seconds=8,
            blink_ms=500,
            refresh_every_blinks=2
    ):
        """
        Live time screen:
          - Blinks every blink_ms
          - Refreshes data every refresh_every_blinks blinks
          - Exits immediately on ANY click if btn provided
        """
        start = time.ticks_ms()
        blink_on = True
        blink_count = 0

        date_str = get_date_str()
        time_str = get_time_str()
        source = get_source()
        temp_c = get_temp_c()

        hold_forever = (max_seconds is None) or (max_seconds <= 0)

        while True:
            blink_on = not blink_on
            blink_count += 1

            if blink_count % max(1, int(refresh_every_blinks)) == 0:
                date_str = get_date_str()
                time_str = get_time_str()
                source = get_source()
                temp_c = get_temp_c()

            self._render(date_str, time_str, source=source, temp_c=temp_c, blink_on=blink_on)

            wait_start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), wait_start) < int(blink_ms):
                if btn is not None:
                    try:
                        action = btn.poll_action()
                        if action:
                            return action
                    except Exception:
                        pass
                time.sleep_ms(20)

            if not hold_forever:
                if time.ticks_diff(time.ticks_ms(), start) >= int(max_seconds * 1000):
                    return None
