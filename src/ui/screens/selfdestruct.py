import time
from src.ui.glyphs import draw_circle  # harmless import if you already use glyphs
from src.ui.faces import draw_face     # uses your face helper (we'll call grin explicitly)


class SelfDestructScreen:
    """
    Easter egg: mock self-destruct sequence.

    Quad click -> this screen.

    Sequence:
      1) 4s: centered arvo20: "Self Destruct Protocol Initiated"
      2) Countdown view:
         - "STAND CLEAR 10M!" (med, centered)
         - countdown number (LARGE font, centered)
         - "CLICK TO ABORT" (med, centered)
         If the user clicks, show "ERROR - ABORT FAILED" for 1s and continue countdown.
      3) Punchline page with GRIN face glyph + "Just kidding!"
         Face is constrained to TOP HALF of the OLED (so it never overlaps the text).
    """

    def __init__(self, oled):
        self.oled = oled

    def _center_text(self, writer, text, y):
        o = self.oled
        text = str(text)
        try:
            w, _ = o._text_size(writer, text)
            x = max(0, (o.width - w) // 2)
        except Exception:
            x = 0
        writer.write(text, x, y)

    def _wait_ms_abortable(self, btn, ms, treat_any_click_as_abort=True):
        """
        Wait ms in small increments.
        Returns True if a click happened during the wait.
        """
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < ms:
            a = btn.poll_action()
            if a is not None:
                if not treat_any_click_as_abort:
                    return True
                if a in ("single", "double", "triple", "quad"):
                    return True
            time.sleep_ms(25)
        return False

    def _draw_countdown_view(self, n, abort_line):
        o = self.oled
        fb = o.oled
        fb.fill(0)

        # Top warning (MED, centered, ALL CAPS)
        self._center_text(o.f_med, "STAND CLEAR 10M!", 0)

        # Big countdown number (use LARGE font from TimeScreen)
        try:
            self._center_text(o.f_large, str(n), 18)
        except Exception:
            try:
                self._center_text(o.f_arvo24, str(n), 20)
            except Exception:
                self._center_text(o.f_arvo20, str(n), 22)

        # Bottom line (MED, centered)
        self._center_text(o.f_med, abort_line, 52)

        fb.show()

    def show(self, btn):
        btn.reset()
        o = self.oled
        fb = o.oled

        # -------------------------------------------------
        # 1) Intro view (4 seconds)
        # -------------------------------------------------
        fb.fill(0)
        self._center_text(o.f_arvo20, "SELF", 18)
        self._center_text(o.f_arvo20, "DESTRUCT", 24)
        self._center_text(o.f_arvo16, "Has been initiated...", 38)
        fb.show()

        self._wait_ms_abortable(btn, 4000, treat_any_click_as_abort=False)
        btn.reset()

        # -------------------------------------------------
        # 2) Countdown view (10..0)
        # -------------------------------------------------
        abort_line = "Click to Abort"
        for n in range(10, -1, -1):
            self._draw_countdown_view(n, abort_line)

            clicked = self._wait_ms_abortable(btn, 1000, treat_any_click_as_abort=True)
            if clicked:
                abort_line = "ERROR--Abort Failed"
                self._draw_countdown_view(n, abort_line)
                self._wait_ms_abortable(btn, 1000, treat_any_click_as_abort=False)
                abort_line = "CLICK TO ABORT"
                btn.reset()

        # -------------------------------------------------
        # 3) Punchline view (GRIN face + Just kidding!)
        #    Face constrained to top half
        # -------------------------------------------------
        fb.fill(0)

        top_h = max(24, int(o.height // 2))  # 32 on 64px OLED; never let it get tiny
        # We'll draw face as if screen height is only top_h,
        # which forces the face radius to fit that band.
        try:
            draw_face(fb, o.width, top_h, "grin", right_edge=False)
        except Exception:
            # fallback: smaller face in top half
            cx = int(o.width // 2)
            cy = int(top_h // 2)
            r = max(10, int(top_h * 0.38))  # ~12 on 32px band

            try:
                fb.ellipse(cx, cy, r, r, 1)
            except Exception:
                try:
                    draw_circle(fb, cx, cy, r)
                except Exception:
                    pass

            # dot eyes
            fb.fill_rect(cx - 7, cy - 5, 3, 3, 1)
            fb.fill_rect(cx + 4, cy - 5, 3, 3, 1)

            # simple "D" grin
            x_left = cx - 10
            x_right = cx + 10
            y_top = cy + 4
            y_bot = cy + 10
            try:
                fb.vline(x_right, y_top, (y_bot - y_top) + 1, 1)
                fb.hline(x_left, y_top, (x_right - x_left), 1)
                fb.hline(x_left, y_bot, (x_right - x_left), 1)
            except Exception:
                # ultra-safe pixel fallback
                for yy in range(y_top, y_bot + 1):
                    fb.pixel(x_right, yy, 1)
                for xx in range(x_left, x_right):
                    fb.pixel(xx, y_top, 1)
                    fb.pixel(xx, y_bot, 1)

        # Reserve bottom for text
        self._center_text(o.f_arvo20, "Just kidding!", 44)
        fb.show()

        # Wait for click to exit
        btn.reset()
        while True:
            a = btn.poll_action()
            if a in ("single", "double", "triple", "quad", "debug"):
                return "next"
            time.sleep_ms(25)
