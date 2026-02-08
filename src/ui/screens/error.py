# src/ui/screens/error.py
# Error screen for AirBuddy
# Pico / MicroPython safe

class ErrorScreen:
    """
    Generic error screen.

    Layout (128x64):

        ⚠
        SENSOR ERROR        ← medium
        Failed to read air  ← small
        E-SENS-01           ← very small (optional)

    Features:
      - Icon (Unicode if available, ASCII fallback)
      - Title (MED font)
      - Message (SMALL font)
      - Optional error code (VSMALL, bottom)
    """

    def __init__(self, oled):
        self.oled = oled

        # Fonts (graceful fallback chain)
        self.f_med = getattr(oled, "f_med", None)
        self.f_small = getattr(oled, "f_small", None)
        self.f_vs = getattr(oled, "f_vsmall", None)

        # Icon choices
        self.icon_unicode = "⚠"
        self.icon_ascii = "!"

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def show(
            self,
            title="Error",
            message="Something went wrong",
            code=None,
            icon=True,
    ):
        """
        Render the error screen.

        title:   short title (MED font)
        message: one-line explanation (SMALL font)
        code:    optional error code string (VSMALL font)
        icon:    True to show warning icon
        """

        fb = getattr(self.oled, "oled", None)
        if fb is None:
            return

        fb.fill(0)

        y = 4  # running vertical cursor

        # ----------------------------
        # Icon
        # ----------------------------
        if icon and self.f_med:
            icon_char = self.icon_unicode
            try:
                # Test render width; some fonts don't include ⚠
                w, _ = self.f_med.size(icon_char)
                if w <= 0:
                    raise ValueError
            except Exception:
                icon_char = self.icon_ascii

            iw, ih = self.f_med.size(icon_char)
            ix = (self.oled.width - iw) // 2
            self.f_med.write(icon_char, ix, y)
            y += ih + 2

        # ----------------------------
        # Title
        # ----------------------------
        if self.f_med:
            tw, th = self.f_med.size(title)
            tx = (self.oled.width - tw) // 2
            self.f_med.write(title, tx, y)
            y += th + 2

        # ----------------------------
        # Message
        # ----------------------------
        if self.f_small:
            mw, mh = self.f_small.size(message)
            mx = (self.oled.width - mw) // 2
            self.f_small.write(message, mx, y)
            y += mh + 4

        # ----------------------------
        # Error code (bottom)
        # ----------------------------
        if code and self.f_vs:
            cw, ch = self.f_vs.size(code)
            cx = (self.oled.width - cw) // 2
            cy = self.oled.height - ch - 2
            self.f_vs.write(code, cx, cy)

        fb.show()
