# src/ui/waiting.py  (MicroPython / Pico-safe)
#
# Waiting / idle screen renderer:
#   - airBuddy logo (bitmap module)
#   - tagline text (MED font)
#   - optional animated dots ("." ".." "..." then blank), 1 step per second

import time
from src.ui import logo_airbuddy


class WaitingScreen:
    def __init__(self, flip_x=False, flip_y=True, gap=6):
        # These flips match what worked for your logo in Booter + OLED
        self.flip_x = flip_x
        self.flip_y = flip_y
        self.gap = gap

        # animation state
        self._start_ms = None

    # ----------------------------
    # PUBLIC API (uniform screen interface)
    # ----------------------------
    def show(self, oled, line="Know your air...", animate=False, period_ms=1000):
        """
        Public entry point used by main.py and other callers.
        """
        self.render(oled, line=line, animate=animate, period_ms=period_ms)

    # ----------------------------
    # Logo helpers (pixel-accurate; avoids MONO_VLSB blit confusion)
    # ----------------------------
    def _logo_pixel(self, data, lw, x, y):
        idx = x + (y >> 3) * lw
        b = data[idx]
        return (b >> (y & 7)) & 1

    def _blit_logo_fixed(self, oled, x0, y0):
        lw = int(getattr(logo_airbuddy, "WIDTH", 0))
        lh = int(getattr(logo_airbuddy, "HEIGHT", 0))
        data = getattr(logo_airbuddy, "DATA", None)

        if (lw <= 0) or (lh <= 0) or (data is None):
            return False

        if not isinstance(data, (bytes, bytearray)):
            try:
                data = bytes(data)
            except Exception:
                return False

        sw = int(getattr(oled, "width", 128))
        sh = int(getattr(oled, "height", 64))

        fb = getattr(oled, "oled", None)
        if fb is None:
            return False

        for yy in range(lh):
            dy = (lh - 1 - yy) if self.flip_y else yy
            sy = y0 + yy
            if sy < 0 or sy >= sh:
                continue

            for xx in range(lw):
                dx = (lw - 1 - xx) if self.flip_x else xx
                sx = x0 + xx
                if sx < 0 or sx >= sw:
                    continue

                if self._logo_pixel(data, lw, dx, dy):
                    fb.pixel(sx, sy, 1)

        return True

    # ----------------------------
    # Time helpers (wrap-safe)
    # ----------------------------
    def _now_ms(self):
        try:
            return time.ticks_ms()
        except Exception:
            return int(time.time() * 1000)

    def _elapsed_ms(self, now_ms):
        """
        Wrap-safe elapsed time in ms.
        """
        if self._start_ms is None:
            self._start_ms = now_ms
            return 0
        try:
            return time.ticks_diff(now_ms, self._start_ms)
        except Exception:
            return now_ms - self._start_ms

    def _anim_step(self, period_ms=1000):
        """
        Returns 0..4:
          0: "."
          1: ".."
          2: "..."
          3: ""   (blank pause)
          4: ""   (blank pause)
        """
        now = self._now_ms()
        elapsed = self._elapsed_ms(now)
        return int(elapsed // int(period_ms)) % 5

    def _animated_line(self, base, period_ms=1000):
        step = self._anim_step(period_ms)
        if step == 0:
            return base + "."
        if step == 1:
            return base + ".."
        if step == 2:
            return base + "..."
        return base

    # ----------------------------
    # Core renderer
    # ----------------------------
    def render(self, oled, line="Know your air...", animate=False, period_ms=1000):
        fb = getattr(oled, "oled", None)
        if fb is None:
            return

        fb.fill(0)

        writer = getattr(oled, "f_med", None) or getattr(oled, "f_small", None)
        if writer is None:
            return

        if animate:
            base = line.rstrip(". ")
            line_to_draw = self._animated_line(base, period_ms)
        else:
            line_to_draw = line

        lw = int(getattr(logo_airbuddy, "WIDTH", 0))
        lh = int(getattr(logo_airbuddy, "HEIGHT", 0))
        use_logo = (lw > 0 and lh > 0 and lw <= oled.width and lh <= oled.height)

        _, line_h = writer.size(line_to_draw)

        total_h = (lh + self.gap + line_h) if use_logo else line_h
        y0 = max(0, (oled.height - total_h) // 2)

        if use_logo:
            logo_x = max(0, (oled.width - lw) // 2)
            ok = self._blit_logo_fixed(oled, logo_x, y0)
            line_y = y0 + lh + self.gap if ok else y0
        else:
            line_y = y0

        oled.draw_centered(writer, line_to_draw, line_y)
        fb.show()
