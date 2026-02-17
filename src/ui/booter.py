# src/ui/booter.py  (MicroPython / Pico-safe)
import time
from src.ui import logo_airbuddy
from src.ui.thermobar import ThermoBar


class Booter:
    """
    Boot screen with real-step progress + mpremote logging.

    - boot_pipeline(steps): step-by-step progress bar + footer text + logs
    - show(duration,fps): legacy smooth bar animation (used for sensor warmup)
      (This method was missing and caused: AttributeError: no attribute 'show')
    """

    def __init__(self, oled):
        self.oled = oled

        # Footer text in MED now
        self.f_footer = (
                getattr(oled, "f_med", None)
                or getattr(oled, "f_arvo16", None)
                or getattr(oled, "f_small", None)
        )

        # Version (shown only at intro)
        self.version = "version 2.1.16"

        # Logo orientation
        self.logo_flip_x = False
        self.logo_flip_y = True

        self.bar = ThermoBar(oled)
        self._layout = None

        # footer truncation
        self._footer_max_chars = 26

    # -------------------------------------------------
    # Framebuffer helpers
    # -------------------------------------------------
    def _fb(self):
        return getattr(self.oled, "oled", None)

    def _clear(self):
        fb = self._fb()
        if fb:
            fb.fill(0)

    def _show_fb(self):
        fb = self._fb()
        if fb:
            fb.show()

    # -------------------------------------------------
    # Text helpers
    # -------------------------------------------------
    def _draw_centered_text_shadow(self, writer, text, y):
        if not writer or text is None:
            return
        text = str(text)

        w = int(getattr(self.oled, "width", 128))
        try:
            tw, _ = writer.size(text)
        except Exception:
            tw = len(text) * 6
        x = max(0, (w - tw) // 2)

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
    # Layout calc (cached)
    # -------------------------------------------------
    def _calc_layout(self):
        w = int(getattr(self.oled, "width", 128))
        h = int(getattr(self.oled, "height", 64))

        gap_logo_to_bar = 4
        gap_bar_to_footer = 4

        lw = int(getattr(logo_airbuddy, "WIDTH", 0))
        lh = int(getattr(logo_airbuddy, "HEIGHT", 0))

        bar_w = int(w * 0.70)
        if bar_w < 40:
            bar_w = 40
        if bar_w > w:
            bar_w = w

        bar_x = max(0, (w - bar_w) // 2)
        bar_h = 7

        footer_h = 10
        if self.f_footer:
            try:
                _, footer_h = self.f_footer.size("Booting")
            except Exception:
                footer_h = 10

        total_h = lh + gap_logo_to_bar + bar_h + gap_bar_to_footer + footer_h
        y0 = max(0, (h - total_h) // 2)

        logo_y = y0
        bar_y = y0 + lh + gap_logo_to_bar
        footer_y = bar_y + bar_h + gap_bar_to_footer

        return {
            "w": w, "h": h,
            "lw": lw, "lh": lh,
            "bar_x": bar_x, "bar_y": bar_y, "bar_w": bar_w,
            "logo_y": logo_y,
            "footer_y": footer_y,
        }

    # -------------------------------------------------
    # Draw frame
    # -------------------------------------------------
    def _draw_frame(self, p=0.0, footer=None):
        if self._layout is None:
            self._layout = self._calc_layout()

        w = self._layout["w"]
        lw = self._layout["lw"]
        bar_x = self._layout["bar_x"]
        bar_y = self._layout["bar_y"]
        bar_w = self._layout["bar_w"]
        logo_y = self._layout["logo_y"]
        footer_y = self._layout["footer_y"]

        self._clear()

        if lw and (lw <= w):
            self._blit_logo_fixed(max(0, (w - lw) // 2), logo_y)

        self.bar.draw(bar_x, bar_y, bar_w, p=max(0.0, min(1.0, float(p))))

        if footer and self.f_footer:
            s = str(footer)
            if len(s) > self._footer_max_chars:
                s = s[:self._footer_max_chars]
            self._draw_centered_text_shadow(self.f_footer, s, footer_y)

        self._show_fb()

    # -------------------------------------------------
    # ✅ Legacy warmup animation (used by src/app/main.py)
    # -------------------------------------------------
    def show(self, duration=4.0, fps=18, footer=None):
        """
        Smooth progress bar animation (no steps), for warmups.
        """
        self._layout = self._calc_layout()

        frames = max(1, int(float(duration) * float(fps)))
        delay_ms = int(1000 / max(1, int(fps)))

        # Start at 0
        self._draw_frame(p=0.0, footer=footer or self.version)

        for i in range(frames + 1):
            p = i / float(frames)
            self._draw_frame(p=p, footer=footer)
            time.sleep_ms(delay_ms)

    # -------------------------------------------------
    # Boot pipeline
    # -------------------------------------------------
    def boot_pipeline(self, steps, intro_ms=500, fps=18, settle_ms=120, logger=None):
        if logger is None:
            logger = print

        self._layout = self._calc_layout()

        # Intro
        self._draw_frame(p=0.0, footer=self.version)
        logger("[BOOT] " + self.version)
        time.sleep_ms(intro_ms)

        try:
            total = len(steps)
        except Exception:
            total = 0

        if total <= 0:
            self._draw_frame(p=1.0, footer="Locked & loaded!")
            logger("[BOOT] Locked & loaded!")
            time.sleep_ms(settle_ms)
            return {"ok": True, "results": []}

        results = []
        p_prev = 0.0

        for idx, item in enumerate(steps):
            try:
                label, fn = item
            except Exception:
                label, fn = ("Step", None)

            label = str(label)

            self._draw_frame(p=p_prev, footer=label)
            logger("[BOOT] " + label)
            time.sleep_ms(settle_ms)

            ok = True
            detail = None

            try:
                if callable(fn):
                    ret = fn()
                    if isinstance(ret, tuple) and len(ret) >= 1:
                        ok = bool(ret[0])
                        if len(ret) >= 2:
                            detail = ret[1]
                    elif isinstance(ret, str):
                        ok = True
                        detail = ret
                    elif isinstance(ret, bool):
                        ok = ret
                else:
                    ok = False
                    detail = "no-fn"
            except Exception as e:
                ok = False
                detail = "err:" + repr(e)
                logger("[BOOT] EXC in " + label + ": " + repr(e))

            results.append({"label": label, "ok": ok, "detail": detail})

            p_next = float(idx + 1) / float(total)

            ramp_frames = max(3, int(fps * 0.12))
            for j in range(ramp_frames):
                pj = p_prev + (p_next - p_prev) * ((j + 1) / float(ramp_frames))
                footer = detail if detail else label
                self._draw_frame(p=pj, footer=footer)
                time.sleep_ms(int(1000 / max(1, fps)))

            status = "OK" if ok else "FAIL"
            if detail:
                logger("[BOOT] " + label + " -> " + status + " " + str(detail))
            else:
                logger("[BOOT] " + label + " -> " + status)

            p_prev = p_next

        self._draw_frame(p=1.0, footer="Locked & loaded!")
        logger("[BOOT] Locked & loaded!")
        time.sleep_ms(settle_ms)

        all_ok = True
        for r in results:
            if not r.get("ok", True):
                all_ok = False
                break

        return {"ok": all_ok, "results": results}
