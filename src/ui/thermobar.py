# src/ui/thermobar.py  (MicroPython / Pico-safe)
#
# A reusable “thermo bar” UI primitive for SSD1306 framebuf displays.
#
# Spec:
#   - Total height: 7px
#   - 1px border
#   - 5px inner fill area
#   - Rounded corners (simple 2px-radius look)
#   - Inner fill uses checkerboard dithering
#   - Leading edge of the fill is a solid vertical line
#
# Usage:
#   bar = ThermoBar(oled)                 # oled is your OLED helper (has .oled FrameBuffer)
#   bar.draw(x=10, y=40, w=108, p=0.65)   # p in [0..1]
#   oled.oled.show()

class ThermoBar:
    H_TOTAL = 7
    BORDER = 1
    INNER_H = 5

    def __init__(self, oled, invert=False):
        """
        oled: your OLED helper. Must expose FrameBuffer as oled.oled with
              .pixel/.hline/.vline/.rect/.fill_rect
        invert: if True, swaps colors (useful for inverted themes)
        """
        self.oled = oled
        self.invert = invert

    # ----------------------------
    # Internal framebuffer helpers
    # ----------------------------
    def _fb(self):
        return getattr(self.oled, "oled", None)

    def _c(self, on):
        # 1-bit display color helper
        if self.invert:
            return 0 if on else 1
        return 1 if on else 0

    def _pixel(self, x, y, on):
        fb = self._fb()
        if fb:
            fb.pixel(int(x), int(y), self._c(on))

    def _hline(self, x, y, w, on):
        fb = self._fb()
        if fb and hasattr(fb, "hline"):
            fb.hline(int(x), int(y), int(w), self._c(on))

    def _vline(self, x, y, h, on):
        fb = self._fb()
        if fb and hasattr(fb, "vline"):
            fb.vline(int(x), int(y), int(h), self._c(on))

    def _fill_rect(self, x, y, w, h, on):
        fb = self._fb()
        if fb and hasattr(fb, "fill_rect"):
            fb.fill_rect(int(x), int(y), int(w), int(h), self._c(on))

    # ----------------------------
    # Rounded outline (7px high, 2px-radius look)
    # ----------------------------
    def _round_rect_outline(self, x, y, w, h, on):
        # h should be 7 in our spec, but keep general.
        # Radius=2 look: we "cut" the extreme corner pixels and draw near-corner pixels.
        if w < 4 or h < 4:
            # fallback
            fb = self._fb()
            if fb and hasattr(fb, "rect"):
                fb.rect(int(x), int(y), int(w), int(h), self._c(on))
            return

        # Top/bottom lines (leave 2px for rounding)
        self._hline(x + 2, y, w - 4, on)
        self._hline(x + 2, y + h - 1, w - 4, on)

        # Left/right lines (leave 2px for rounding)
        self._vline(x, y + 2, h - 4, on)
        self._vline(x + w - 1, y + 2, h - 4, on)

        # Corner pixels to suggest radius=2
        # Top-left
        self._pixel(x + 1, y, on)
        self._pixel(x, y + 1, on)
        # Top-right
        self._pixel(x + w - 2, y, on)
        self._pixel(x + w - 1, y + 1, on)
        # Bottom-left
        self._pixel(x, y + h - 2, on)
        self._pixel(x + 1, y + h - 1, on)
        # Bottom-right
        self._pixel(x + w - 1, y + h - 2, on)
        self._pixel(x + w - 2, y + h - 1, on)

    # ----------------------------
    # Public API
    # ----------------------------
    def clear(self, x, y, w):
        """
        Clears the full bar area (including border).
        """
        self._fill_rect(x, y, w, self.H_TOTAL, on=False)

    def draw(self, x, y, w, p, outline=True, clear_bg=True):
        """
        Draw a 7px-high thermo bar.

        x,y: top-left
        w:   total width in pixels
        p:   progress 0..1
        outline: draw the 1px rounded border
        clear_bg: clears the bar area first (recommended when animating)

        Inner fill:
          - 5px tall
          - inset by 2px horizontally (looks nicer with rounded corners)
          - checkerboard dither
          - solid leading edge
        """
        fb = self._fb()
        if fb is None:
            return

        # Clamp width and progress
        if w < 10:
            w = 10
        if p < 0:
            p = 0
        elif p > 1:
            p = 1

        h = self.H_TOTAL

        if clear_bg:
            self._fill_rect(x, y, w, h, on=False)

        # Border
        if outline:
            self._round_rect_outline(x, y, w, h, on=True)

        # Inner fill geometry:
        # - 1px border top/bottom => inner band is y+1 .. y+5 (5px)
        # - 2px horizontal inset (requested “2px inset” feel)
        inner_y = y + self.BORDER
        inner_h = self.INNER_H

        inner_x = x + 2
        inner_w = w - 4
        if inner_w < 1:
            return

        # Compute filled width
        fill_w = int(inner_w * p)
        if fill_w <= 0:
            return

        # Dither fill (checkerboard) across fill_w
        # We draw pixels rather than fill_rect to create the pattern.
        for yy in range(inner_y, inner_y + inner_h):
            for xx in range(inner_x, inner_x + fill_w):
                # Checkerboard: alternate pixels
                on = ((xx + yy) & 1) == 0
                if on:
                    self._pixel(xx, yy, True)

        # Solid leading edge (straight vertical line at the fill front)
        lead_x = inner_x + fill_w - 1
        if lead_x >= inner_x:
            self._vline(lead_x, inner_y, inner_h, on=True)
