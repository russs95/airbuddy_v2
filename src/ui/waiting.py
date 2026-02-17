# src/ui/waiting.py  (MicroPython / Pico-safe)
#
# Waiting / idle screen renderer:
#   - airBuddy logo (bitmap module)
#   - tagline text (MED font)
#   - optional animated dots ("." ".." "..." then blank), 1 step per second
#   - status icons (top-right):
#       WiFi (compact) (solid when on, hollow when off)
#       GPS  (compact text) shown when gps_on
#       API  (ring+dot when on, ring only when off)
#
# PATCH (UI tweaks):
# - Raise airBuddy logo by 5px
# - Raise "Know your air..." line by 7px
# - Reduce left margin of API indicator by 2px (moves it right)
#
# PATCH (RAM tightening):
# - Cache logo WIDTH/HEIGHT/DATA as bytes once (avoid bytes() allocation each render)
# - Reduce repeated getattr() churn in render path
# - Keep allocations low in animation + centering helpers

import time
import gc
from src.ui import logo_airbuddy
from src.ui.glyphs import draw_wifi, draw_gps, draw_api


class WaitingScreen:
    def __init__(self, flip_x=False, flip_y=True, gap=6, logo_drop_px=10):
        # These flips match what worked for your logo in Booter + OLED
        self.flip_x = flip_x
        self.flip_y = flip_y
        self.gap = int(gap)
        self.logo_drop_px = int(logo_drop_px)

        # animation state
        self._start_ms = None

        # logo cache (RAM saving: convert DATA -> bytes once)
        self._logo_lw = None
        self._logo_lh = None
        self._logo_data = None  # bytes/bytearray

        # UI tweaks
        self._logo_raise_px = 5
        self._line_raise_px = 7

    # ----------------------------
    # PUBLIC API
    # ----------------------------
    def show(
            self,
            oled,
            line="Know your air...",
            animate=False,
            period_ms=1000,
            *,
            wifi_ok=False,
            gps_on=False,
            api_ok=False
    ):
        self.render(
            oled,
            line=line,
            animate=animate,
            period_ms=period_ms,
            wifi_ok=wifi_ok,
            gps_on=gps_on,
            api_ok=api_ok
        )

    # ----------------------------
    # Logo helpers (pixel-accurate)
    # ----------------------------
    def _get_logo_cached(self):
        """
        Cache WIDTH/HEIGHT/DATA as bytes once to avoid allocations each render.
        Returns (lw, lh, data_bytes) or (0, 0, None) if unavailable.
        """
        if self._logo_lw is not None:
            return self._logo_lw, self._logo_lh, self._logo_data

        lw = int(getattr(logo_airbuddy, "WIDTH", 0) or 0)
        lh = int(getattr(logo_airbuddy, "HEIGHT", 0) or 0)
        data = getattr(logo_airbuddy, "DATA", None)

        if (lw <= 0) or (lh <= 0) or (data is None):
            self._logo_lw, self._logo_lh, self._logo_data = 0, 0, None
            return 0, 0, None

        # Ensure bytes/bytearray (avoid repeated bytes() allocations later)
        if not isinstance(data, (bytes, bytearray)):
            try:
                data = bytes(data)
            except Exception:
                self._logo_lw, self._logo_lh, self._logo_data = 0, 0, None
                return 0, 0, None

        self._logo_lw, self._logo_lh, self._logo_data = lw, lh, data
        return lw, lh, data

    def _logo_pixel(self, data, lw, x, y):
        idx = x + (y >> 3) * lw
        b = data[idx]
        return (b >> (y & 7)) & 1

    def _blit_logo_fixed(self, oled, x0, y0, lw, lh, data):
        sw = int(getattr(oled, "width", 128))
        sh = int(getattr(oled, "height", 64))

        fb = getattr(oled, "oled", None)
        if fb is None:
            return False

        # Bounds clipping happens per pixel to keep it simple + safe.
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
        if self._start_ms is None:
            self._start_ms = now_ms
            return 0
        try:
            return time.ticks_diff(now_ms, self._start_ms)
        except Exception:
            return now_ms - self._start_ms

    def _anim_step(self, period_ms=1000):
        now = self._now_ms()
        elapsed = self._elapsed_ms(now)
        p = int(period_ms) or 1000
        return int(elapsed // p) % 5

    def _animated_line(self, base, period_ms=1000):
        # Keep allocations minimal
        step = self._anim_step(period_ms)
        if step == 0:
            return base + "."
        if step == 1:
            return base + ".."
        if step == 2:
            return base + "..."
        return base

    # ----------------------------
    # Safe text sizing + centering (prevents ezFBfont MemoryError)
    # ----------------------------
    def _safe_text_size(self, writer, text):
        """
        Try writer.size(). If it allocates too much (ezFBfont),
        fall back to fixed-width guess to avoid MemoryError.
        """
        text = str(text or "")
        try:
            return writer.size(text)
        except MemoryError:
            return (len(text) * 6, 8)
        except Exception:
            return (len(text) * 6, 8)

    def _safe_center_write(self, oled, writer, text, y):
        text = str(text or "")
        w = int(getattr(oled, "width", 128))
        tw, _ = self._safe_text_size(writer, text)
        x = max(0, (w - int(tw)) // 2)
        try:
            writer.write(text, x, int(y))
        except MemoryError:
            # Last resort: write left aligned
            try:
                writer.write(text, 0, int(y))
            except Exception:
                pass
        except Exception:
            pass

    # ----------------------------
    # Status icons (top-right)
    # ----------------------------
    def _draw_status_icons(self, oled, wifi_ok=False, gps_on=False, api_ok=False):
        """
        Right-aligned icon cluster in top-right corner.
        Order (left->right): API, GPS, WiFi
        """
        fb = getattr(oled, "oled", None)
        if fb is None:
            return

        w = int(getattr(oled, "width", 128))
        y = 1
        margin = 1
        gap = 3

        # PATCH: reduce API "left margin" by 2px => move API right by 2px
        # (was 4, now 2)
        api_extra_gap = 2

        x = w - margin

        # WiFi (9x6)
        x -= 9
        try:
            draw_wifi(fb, x, y, on=bool(wifi_ok), color=1)
        except Exception:
            pass
        x -= gap

        # GPS (14x6) only if gps_on
        if gps_on:
            x -= 14
            try:
                draw_gps(fb, x, y, color=1)
            except Exception:
                pass
            x -= gap

        # API (7x7) always drawn (hollow if off)
        x -= (7 + api_extra_gap)
        try:
            draw_api(fb, x, y, on=bool(api_ok), color=1)
        except Exception:
            pass

    # ----------------------------
    # Core renderer
    # ----------------------------
    def render(
            self,
            oled,
            line="Know your air...",
            animate=False,
            period_ms=1000,
            *,
            wifi_ok=False,
            gps_on=False,
            api_ok=False
    ):
        fb = getattr(oled, "oled", None)
        if fb is None:
            return

        # Avoid extra attribute lookups
        ow = int(getattr(oled, "width", 128))
        oh = int(getattr(oled, "height", 64))

        fb.fill(0)

        writer = getattr(oled, "f_med", None) or getattr(oled, "f_small", None)
        if writer is None:
            return

        # Draw icons first
        self._draw_status_icons(oled, wifi_ok=wifi_ok, gps_on=gps_on, api_ok=api_ok)

        # Animated line (minimal allocations)
        if animate:
            base = (line or "").rstrip(". ")
            line_to_draw = self._animated_line(base, period_ms)
        else:
            line_to_draw = line or ""

        # Logo cache
        lw, lh, data = self._get_logo_cached()
        use_logo = (lw > 0 and lh > 0 and lw <= ow and lh <= oh and data is not None)

        _, line_h = self._safe_text_size(writer, line_to_draw)
        total_h = (lh + self.gap + line_h) if use_logo else line_h
        y0 = max(0, (oh - total_h) // 2)

        # Original drop, then PATCH: raise logo by 5px (net effect: y0 + drop - raise)
        y0 = y0 + self.logo_drop_px - self._logo_raise_px

        if use_logo:
            logo_x = max(0, (ow - lw) // 2)
            ok = self._blit_logo_fixed(oled, logo_x, y0, lw, lh, data)

            # Base line position below logo
            line_y = (y0 + lh + self.gap) if ok else y0
        else:
            line_y = y0

        # PATCH: raise "Know your air..." by 7px
        line_y = max(0, int(line_y) - self._line_raise_px)

        # Safe centered write (no ezFBfont allocations)
        self._safe_center_write(oled, writer, line_to_draw, line_y)

        fb.show()

        # small GC nudge — helps after network spikes
        try:
            gc.collect()
        except Exception:
            pass
