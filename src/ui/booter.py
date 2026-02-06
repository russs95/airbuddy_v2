# src/ui/booter.py  (MicroPython / Pico-safe)
import time

from src.ui import logo_airbuddy
from src.ui.thermobar import ThermoBar


class Booter:
    """
    Boot screen for Pico (SSD1306 OLED):

      - Logo bitmap (fixed orientation via pixel blit)
      - Loading bar: ThermoBar (7px tall: 1px border + 5px inner)
      - Version centered under bar (SMALL font, with optional subtle “shadow” for legibility)
      - Default duration: 5 seconds
    """

    def __init__(self, oled):
        self.oled = oled

        # Use SMALL for version so it's readable
        self.f_ver = getattr(oled, "f_small", None)

        # Version string
        self.version = "version 2.1.1"

        # Logo transform (current working orientation)
        self.logo_flip_x = False
        self.logo_flip_y = True

        # ThermoBar instance (reusable)
        self.bar = ThermoBar(oled)

    # ----------------------------
    # Framebuffer helpers
    # ----------------------------
    def _fb(self):
        return getattr(self.oled, "oled", None)

    def _clear(self):
        fb = self._fb()
        if fb and hasattr(fb, "fill"):
            fb.fill(0)
        elif hasattr(self.oled, "clear"):
            self.oled.clear()

    def _show(self):
        fb = self._fb()
        if fb and hasattr(fb, "show"):
            fb.show()
        elif hasattr(self.oled, "show"):
            self.oled.show()

    # ----------------------------
    # Text helpers
    # ----------------------------
    def _draw_centered_text(self, writer, text, y):
        if not writer:
            return
        w = int(getattr(self.oled, "width", 128))
        tw, _ = writer.size(text)
        x = max(0, (w - tw) // 2)
        writer.write(text, x, y)

    def _draw_centered_text_shadow(self, writer, text, y):
        """
        Improves legibility on OLED by adding a tiny 1px shadow/outline feel.
        On monochrome this is subtle, but it helps on thin fonts.
        """
        if not writer:
            return
        w = int(getattr(self.oled, "width", 128))
        tw, _ = writer.size(text)
        x = max(0, (w - tw) // 2)

        # "Shadow" by drawing once offset in black, then normal in white.
        # We do this by temporarily using bg/fg via writer overrides.
        # If your ezFBfont doesn't support fg/bg override, it will just draw normally.
        try:
            writer.write(text, x + 1, y + 1, fg=0, bg=0)
        except Exception:
            pass
        writer.write(text, x, y)

    # ----------------------------
    # Logo draw (robust, fixes flips)
    # ----------------------------
    def _logo_pixel(self, data, lw, x, y):
        idx = x + (y >> 3) * lw
        b = data[idx]
        return (b >> (y & 7)) & 1

    def _blit_logo_fixed(self, x0, y0):
        fb = self._fb()
        if fb is None:
            return

        lw = int(getattr(logo_airbuddy, "WIDTH", 0))
        lh = int(getattr(logo_airbuddy, "HEIGHT", 0))
        data = getattr(logo_airbuddy, "DATA", None)

        if (lw <= 0) or (lh <= 0) or (data is None):
            return

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
            if sy < 0 or sy >= sh:
                continue

            for xx in range(lw):
                dx = (lw - 1 - xx) if self.logo_flip_x else xx
                sx = x0 + xx
                if sx < 0 or sx >= sw:
                    continue

                if self._logo_pixel(data, lw, dx, dy):
                    fb.pixel(sx, sy, 1)

    # ----------------------------
    # Main
    # ----------------------------
    def show(self, duration=5.0, fps=18):
        """
        duration: total boot animation time (seconds). Default 5.0s
        fps: animation frame rate. 18 is smooth on SSD1306 without being too heavy.
        """
        w = int(getattr(self.oled, "width", 128))
        h = int(getattr(self.oled, "height", 64))

        # Layout constants
        gap_logo_to_bar = 4
        gap_bar_to_ver = 4
        margin = 8

        # Logo metrics
        lw = int(getattr(logo_airbuddy, "WIDTH", 0))
        lh = int(getattr(logo_airbuddy, "HEIGHT", 0))
        use_logo = (lw > 0 and lh > 0 and lw <= w and lh <= h)

        # Version metrics
        ver_h = 8
        if self.f_ver:
            _, ver_h = self.f_ver.size(self.version)

        # ThermoBar geometry
        bar_h = self.bar.H_TOTAL  # 7px
        bar_w = max(40, w - 2 * margin)
        bar_x = (w - bar_w) // 2
        if bar_x < 0:
            bar_x = 0

        # Total block height
        top_h = lh if use_logo else 12
        total_h = top_h + gap_logo_to_bar + bar_h + gap_bar_to_ver + ver_h
        y0 = (h - total_h) // 2
        if y0 < 0:
            y0 = 0

        logo_y = y0
        bar_y = y0 + top_h + gap_logo_to_bar
        ver_y = bar_y + bar_h + gap_bar_to_ver

        # Static draw
        self._clear()

        # Logo centered
        if use_logo:
            logo_x = (w - lw) // 2
            if logo_x < 0:
                logo_x = 0
            self._blit_logo_fixed(logo_x, logo_y)

        # Draw initial empty bar + version
        self.bar.draw(bar_x, bar_y, bar_w, p=0.0, outline=True, clear_bg=False)

        # Version centered with slight shadow to improve readability
        if self.f_ver:
            self._draw_centered_text_shadow(self.f_ver, self.version, ver_y)

        self._show()

        # Animate bar LEFT -> RIGHT
        frames = max(1, int(float(duration) * float(fps)))
        frame_delay = 1.0 / max(1.0, float(fps))

        for i in range(frames + 1):
            p = i / float(frames)

            # Only redraw bar area (fast, minimal flicker)
            self.bar.draw(bar_x, bar_y, bar_w, p=p, outline=True, clear_bg=True)

            # Re-draw version (bar clear_bg won't touch it, but safe)
            if self.f_ver:
                # Clear a thin band behind the version to prevent any ghosting
                # (optional; comment out if you prefer)
                fb = self._fb()
                if fb and hasattr(fb, "fill_rect"):
                    fb.fill_rect(0, int(ver_y), int(w), int(ver_h), 0)
                self._draw_centered_text_shadow(self.f_ver, self.version, ver_y)

            self._show()
            time.sleep(frame_delay)
