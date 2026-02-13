# src/ui/booter.py  (MicroPython / Pico-safe)
import time
from src.ui import logo_airbuddy
from src.ui.thermobar import ThermoBar


class Booter:
    """
    Boot screen (cosmetic only).

    - airBuddy logo
    - ThermoBar progress animation
    - Version text
    - Fixed-duration animation (default 5s)

    NOTE:
      Sensor warm-up should be started by main.py BEFORE calling show().
    """

    def __init__(self, oled):
        self.oled = oled
        self.f_ver = getattr(oled, "f_small", None)

        # Updated version text
        self.version = "version 2.1.14"

        # Logo orientation (confirmed working)
        self.logo_flip_x = False
        self.logo_flip_y = True

        self.bar = ThermoBar(oled)

    # -------------------------------------------------
    # Framebuffer helpers
    # -------------------------------------------------
    def _fb(self):
        return getattr(self.oled, "oled", None)

    def _clear(self):
        fb = self._fb()
        if fb:
            fb.fill(0)

    def _show(self):
        fb = self._fb()
        if fb:
            fb.show()

    # -------------------------------------------------
    # Text helpers
    # -------------------------------------------------
    def _draw_centered_text_shadow(self, writer, text, y):
        if not writer:
            return
        w = int(getattr(self.oled, "width", 128))
        tw, _ = writer.size(text)
        x = max(0, (w - tw) // 2)

        # subtle shadow (1px offset)
        writer.write(text, x + 1, y + 1)
        writer.write(text, x, y)

    # -------------------------------------------------
    # Logo blit (pixel-safe)
    # -------------------------------------------------
    def _logo_pixel(self, data, lw, x, y):
        idx = x + (y >> 3) * lw
        return (data[idx] >> (y & 7)) & 1

    def _blit_logo_fixed(self, x0, y0):
        fb = self._fb()
        if not fb:
            return

        lw = int(getattr(logo_airbuddy, "WIDTH", 0))
        lh = int(getattr(logo_airbuddy, "HEIGHT", 0))
        data = getattr(logo_airbuddy, "DATA", None)

        if (lw <= 0) or (lh <= 0) or (data is None):
            return

        # ensure bytes-like
        if not isinstance(data, (bytes, bytearray)):
            try:
                data = bytes(data)
            except Exception:
                return

        sw = int(getattr(self.oled, "width", 128))
        sh = int(getattr(self.oled, "height", 64))

        for yy in range(lh):
            dy = (lh - 1 - yy) if self.logo_flip_y else yy
            sy = y0 + yy
            if not (0 <= sy < sh):
                continue

            for xx in range(lw):
                dx = (lw - 1 - xx) if self.logo_flip_x else xx
                sx = x0 + xx
                if not (0 <= sx < sw):
                    continue

                if self._logo_pixel(data, lw, dx, dy):
                    fb.pixel(sx, sy, 1)

    # -------------------------------------------------
    # Main animation
    # -------------------------------------------------
    def show(self, duration=5.0, fps=18):
        """
        Fixed-duration cosmetic boot animation.
        Default: 5 seconds.
        """
        w = int(getattr(self.oled, "width", 128))
        h = int(getattr(self.oled, "height", 64))

        gap_logo_to_bar = 4
        gap_bar_to_ver = 4

        lw = int(getattr(logo_airbuddy, "WIDTH", 0))
        lh = int(getattr(logo_airbuddy, "HEIGHT", 0))

        # Bar: 70% of screen width, centered
        bar_w = int(w * 0.70)
        if bar_w < 40:
            bar_w = 40
        if bar_w > w:
            bar_w = w

        bar_x = max(0, (w - bar_w) // 2)
        bar_h = 7  # ThermoBar visual spec

        # Version height
        ver_h = 8
        if self.f_ver:
            _, ver_h = self.f_ver.size(self.version)

        # Center whole block vertically
        total_h = lh + gap_logo_to_bar + bar_h + gap_bar_to_ver + ver_h
        y0 = max(0, (h - total_h) // 2)

        logo_y = y0
        bar_y = y0 + lh + gap_logo_to_bar
        ver_y = bar_y + bar_h + gap_bar_to_ver

        self._clear()

        # Logo
        if lw and lh and (lw <= w) and (lh <= h):
            self._blit_logo_fixed(max(0, (w - lw) // 2), logo_y)

        # Initial bar + version
        self.bar.draw(bar_x, bar_y, bar_w, p=0.0)
        if self.f_ver:
            self._draw_centered_text_shadow(self.f_ver, self.version, ver_y)

        self._show()

        frames = max(1, int(float(duration) * float(fps)))
        frame_delay = 1.0 / max(1.0, float(fps))

        for i in range(frames + 1):
            p = i / float(frames)
            self.bar.draw(bar_x, bar_y, bar_w, p=p)
            self._show()
            time.sleep(frame_delay)
