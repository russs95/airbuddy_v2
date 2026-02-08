# src/ui/screens/time.py — Time + RTC info screen (Pico / MicroPython safe)

class TimeScreen:
    """
    OLED time screen:

      Top (MED):       DD/MM/YYYY (centered)
      Middle (LARGE):  HH:MM (centered)
      Bottom-left:     ⚫RTC  or  ◯SYS  (symbol + label)
      Bottom-right:    27°C  (SMALL)
    """

    def __init__(self, oled):
        self.oled = oled

    def _draw_bottom_left_source(self, source):
        """
        Draws bottom-left: (circle symbol) + label.
        Uses oled.f_sym for the circle and oled.f_small for the text.
        """
        # Choose symbol + label
        source = (source or "SYS").upper()
        if source == "RTC":
            sym = "⚫"
            label = "RTC"
        else:
            sym = "◯"
            label = "SYS"

        # Bottom line placement
        _, h_small = self.oled._text_size(self.oled.f_small, "Ag")
        y = max(0, self.oled.height - h_small - 1)

        x = 2  # left padding

        # Draw symbol (slightly nudged down for visual alignment)
        self.oled.f_sym.write(sym, x, y)

        # Advance x by symbol width + small gap
        w_sym, _ = self.oled._text_size(self.oled.f_sym, sym)
        x += w_sym + 2

        # Draw label
        self.oled.f_small.write(label, x, y)

    def _draw_bottom_right_temp(self, temp_c):
        """
        Draws bottom-right temperature like "27°C" in SMALL font.
        """
        if temp_c is None:
            return

        try:
            t = int(round(float(temp_c)))
        except Exception:
            return

        text = f"{t}°C"

        w, h = self.oled._text_size(self.oled.f_small, text)
        x = max(0, self.oled.width - w - 2)
        y = max(0, self.oled.height - h - 1)
        self.oled.f_small.write(text, x, y)

    def show(self, date_str, time_str, source="SYS", temp_c=None):
        """
        Render the screen.
        date_str: "DD/MM/YYYY" (or "--/--/----")
        time_str: "HH:MM" (or "--:--")
        source: "RTC" or "SYS"
        temp_c: float/int or None
        """
        self.oled.oled.fill(0)

        # --- Top: date (MED, centered) ---
        _, h_med = self.oled._text_size(self.oled.f_med, date_str)
        y_date = 0
        self.oled.draw_centered(self.oled.f_med, date_str, y_date)

        # --- Center: time (LARGE, centered) ---
        # Center it in remaining space, leaving room for bottom line (small font)
        _, h_large = self.oled._text_size(self.oled.f_large, time_str)
        _, h_small = self.oled._text_size(self.oled.f_small, "Ag")

        top_block = y_date + h_med + 2
        bottom_block = self.oled.height - h_small - 2  # leave 1px padding

        available = max(0, bottom_block - top_block)
        y_time = top_block + max(0, (available - h_large) // 2)

        self.oled.draw_centered(self.oled.f_large, time_str, y_time)

        # --- Bottom-left: source ---
        self._draw_bottom_left_source(source)

        # --- Bottom-right: temp ---
        self._draw_bottom_right_temp(temp_c)

        self.oled.oled.show()
