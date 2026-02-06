# src/ui/spinner.py  (MicroPython / Pico-safe)
import time


class Spinner:
    """
    Breathing bar spinner for Pico / SSD1306 (no fonts, no Unicode).

    - Pure pixel drawing on framebuf
    - 1px rounded-ish border (2px corner inset)
    - Inner height: 5px, total height: 7px
    - Center-expanding/contracting fill
    - Checkerboard dithering fill
    - Solid leading edges
    """

    H_TOTAL = 7
    INNER_H = 5

    def __init__(self, oled):
        self.oled = oled

        # Layout
        self.margin = 10
        self.y = 42  # default band y (adjust per your layout)

        # Animation
        self.frame_ms = 45
        self.step_px = 4  # pixels per frame (speed)

    # ----------------------------
    # Framebuffer helpers
    # ----------------------------
    def _fb(self):
        return getattr(self.oled, "oled", None)

    def _show(self):
        fb = self._fb()
        if fb and hasattr(fb, "show"):
            fb.show()
        elif hasattr(self.oled, "show"):
            self.oled.show()

    def _fill_rect(self, x, y, w, h, color):
        fb = self._fb()
        if fb and hasattr(fb, "fill_rect"):
            fb.fill_rect(int(x), int(y), int(w), int(h), int(color))

    def _pixel(self, x, y, color):
        fb = self._fb()
        if fb and hasattr(fb, "pixel"):
            fb.pixel(int(x), int(y), int(color))

    def _hline(self, x, y, w, color):
        fb = self._fb()
        if fb and hasattr(fb, "hline"):
            fb.hline(int(x), int(y), int(w), int(color))

    def _vline(self, x, y, h, color):
        fb = self._fb()
        if fb and hasattr(fb, "vline"):
            fb.vline(int(x), int(y), int(h), int(color))

    # ----------------------------
    # Rounded-ish outline (same style as ThermoBar)
    # ----------------------------
    def _round_rect_outline(self, x, y, w, h, color):
        # Radius=2 look by cutting corner pixels
        if w < 6 or h < 6:
            # fallback
            fb = self._fb()
            if fb and hasattr(fb, "rect"):
                fb.rect(int(x), int(y), int(w), int(h), int(color))
            return

        # top/bottom
        self._hline(x + 2, y, w - 4, color)
        self._hline(x + 2, y + h - 1, w - 4, color)

        # left/right
        self._vline(x, y + 2, h - 4, color)
        self._vline(x + w - 1, y + 2, h - 4, color)

        # corners
        self._pixel(x + 1, y, color)
        self._pixel(x, y + 1, color)

        self._pixel(x + w - 2, y, color)
        self._pixel(x + w - 1, y + 1, color)

        self._pixel(x, y + h - 2, color)
        self._pixel(x + 1, y + h - 1, color)

        self._pixel(x + w - 1, y + h - 2, color)
        self._pixel(x + w - 2, y + h - 1, color)

    # ----------------------------
    # Dither fill with solid leading edges
    # ----------------------------
    def _dither_fill(self, x, y, w, h):
        # checkerboard fill
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                if ((xx + yy) & 1) == 0:
                    self._pixel(xx, yy, 1)

    def _draw_breath_bar(self, x, y, w, phase_w):
        """
        Draw one frame of the breathing bar.

        x,y: outer box top-left
        w: total width of outer box
        phase_w: inner fill width (0..inner_w), centered
        """
        # Outer height fixed
        h = self.H_TOTAL

        # Clear the full bar region first (fast)
        self._fill_rect(x, y, w, h, 0)

        # Outline
        self._round_rect_outline(x, y, w, h, 1)

        # Inner region
        inner_x = x + 2
        inner_y = y + 1
        inner_w = w - 4
        inner_h = self.INNER_H

        if inner_w <= 0:
            return

        # Clamp phase
        if phase_w < 0:
            phase_w = 0
        if phase_w > inner_w:
            phase_w = inner_w

        if phase_w == 0:
            return

        # Centered fill region
        fx = inner_x + (inner_w - phase_w) // 2

        # Dither fill
        self._dither_fill(fx, inner_y, phase_w, inner_h)

        # Solid leading edges (left and right edge of the breathing fill)
        # left edge
        self._vline(fx, inner_y, inner_h, 1)
        # right edge
        self._vline(fx + phase_w - 1, inner_y, inner_h, 1)

    # ----------------------------
    # Public API
    # ----------------------------
    def spin(self, duration=6.0):
        """
        Run breathing spinner animation for `duration` seconds.
        """
        fb = self._fb()
        if fb is None:
            return

        screen_w = int(getattr(self.oled, "width", 128))

        bar_x = self.margin
        bar_w = max(30, screen_w - (self.margin * 2))
        bar_y = int(self.y)

        # Inner width used for phase calculation
        inner_w = bar_w - 4
        if inner_w < 1:
            return

        start = time.ticks_ms()
        end = start + int(duration * 1000)

        # phase oscillates 0..inner_w..0
        phase = 0
        direction = 1

        while time.ticks_diff(end, time.ticks_ms()) > 0:
            phase += direction * self.step_px
            if phase >= inner_w:
                phase = inner_w
                direction = -1
            elif phase <= 0:
                phase = 0
                direction = 1

            # Draw frame
            self._draw_breath_bar(bar_x, bar_y, bar_w, phase)

            self._show()
            time.sleep_ms(self.frame_ms)
