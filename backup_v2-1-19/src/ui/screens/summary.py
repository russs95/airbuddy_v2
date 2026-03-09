# src/ui/screens/summary.py — Summary screen (Pico / MicroPython safe)

import time
from src.ui.glyphs import draw_circle, draw_degree, draw_c, draw_sub2
from src.ui.faces import draw_face


class SummaryScreen:
    def __init__(self, oled):
        self.oled = oled
        self.f = oled.f_med

        self.indent_x = 14
        self.top_y = 4

    # -------------------------------------------------
    # Classification (score + mood)
    # -------------------------------------------------
    def _score_from_reading(self, r):
        """
        Returns lvl 0..4
          0 good, 1 ok, 2 poor, 3 bad, 4 verybad
        """
        ppm = int(getattr(r, "eco2_ppm", 0) or 0)
        tvoc = int(getattr(r, "tvoc_ppb", 0) or 0)
        ready = bool(getattr(r, "ready", True))

        if (not ready) or (ppm <= 0):
            return 2  # "poor" default when not ready

        # --- CO2 severity (0..4) ---
        if ppm < 800:
            co2_lvl = 0
        elif ppm < 1200:
            co2_lvl = 1
        elif ppm < 2000:
            co2_lvl = 2
        elif ppm < 5000:
            co2_lvl = 3
        else:
            co2_lvl = 4

        # --- TVOC severity (0..4) ---
        if tvoc <= 0:
            tvoc_lvl = 0
        elif tvoc < 200:
            tvoc_lvl = 0
        elif tvoc < 600:
            tvoc_lvl = 1
        elif tvoc < 2000:
            tvoc_lvl = 2
        elif tvoc < 5000:
            tvoc_lvl = 3
        else:
            tvoc_lvl = 4

        # Conservative combine: take the worse
        return co2_lvl if co2_lvl > tvoc_lvl else tvoc_lvl

    def _mood_from_score(self, lvl):
        if lvl <= 0:
            return "good"
        if lvl == 1:
            return "ok"
        if lvl == 2:
            return "poor"
        if lvl == 3:
            return "bad"
        return "verybad"

    # -------------------------------------------------
    # Lines
    # -------------------------------------------------
    def _draw_temp_line(self, temp_c, x, y):
        """
        MED: 29.7°C (degree ring pixel + C)
        """
        if temp_c is None:
            self.f.write("--.-", x, y)
            return

        try:
            t = round(float(temp_c), 1)
            num = "{:.1f}".format(t)
        except Exception:
            self.f.write("--.-", x, y)
            return

        self.f.write(num, x, y)
        w_num, _ = self.oled._text_size(self.f, num)

        deg_r = 2
        deg_w = deg_r * 2 + 1
        x_deg = x + int(w_num) + 1
        draw_degree(self.oled.oled, x_deg, y + 3, r=deg_r, color=1)

        x_c = x_deg + deg_w + 1
        if not self.f.write("C", x_c, y):
            draw_c(self.oled.oled, x_c, y + 2, scale=1, color=1)

    def _draw_humidity_line(self, rh, score, x, y):
        """
        MED: 67% | 2
        """
        if rh is None:
            txt = "--% | {}".format(score)
            self.f.write(txt, x, y)
            return

        try:
            rh_i = int(round(float(rh)))
            txt = "{}% | {}".format(rh_i, int(score))
        except Exception:
            txt = "--% | {}".format(score)

        self.f.write(txt, x, y)

    def _draw_co2_line(self, eco2, x, y):
        """
        MED: 638 CO₂
        (CO + sub2 glyph)
        """
        if eco2 is None:
            self.f.write("-- CO", x, y)
            # sub2 after "CO"
            w, _ = self.oled._text_size(self.f, "-- CO")
            draw_sub2(self.oled.oled, x + int(w) + 1, y + 9, scale=1, color=1)
            return

        try:
            n = str(int(eco2))
        except Exception:
            n = "--"

        # write "<n> CO"
        base = "{} CO".format(n)
        self.f.write(base, x, y)

        w_base, _ = self.oled._text_size(self.f, base)
        # subscript sits a bit lower than baseline (tuned for MED)
        draw_sub2(self.oled.oled, x + int(w_base) + 1, y + 9, scale=1, color=1)

    def _draw_tvoc_line(self, tvoc, x, y):
        if tvoc is None:
            self.f.write("-- ppb", x, y)
            return
        try:
            self.f.write(str(int(tvoc)) + " ppb", x, y)
        except Exception:
            self.f.write("-- ppb", x, y)

    def _draw_heartbeat_icon(self, x, y, filled):
        r = 4
        cx = x + r
        cy = y + 6
        draw_circle(self.oled.oled, cx, cy, r=r, filled=filled, color=1)

    # -------------------------------------------------
    # Layout
    # -------------------------------------------------
    def _draw_left_column(self, r, x, y, beat_filled=False):
        _, h = self.oled._text_size(self.f, "Ag")
        line_h = h + 2

        eco2 = getattr(r, "eco2_ppm", None) if r else None
        tvoc = getattr(r, "tvoc_ppb", None) if r else None
        temp_c = getattr(r, "temp_c", None) if r else None
        rh = getattr(r, "humidity", None) if r else None

        score = self._score_from_reading(r) if r else 2

        # CO2 + heartbeat
        self._draw_heartbeat_icon(x=2, y=y, filled=beat_filled)
        self._draw_co2_line(eco2, x, y)
        y += line_h

        # TVOC
        self._draw_tvoc_line(tvoc, x, y)
        y += line_h

        # TEMP
        self._draw_temp_line(temp_c, x, y)
        y += line_h

        # HUMIDITY + score
        self._draw_humidity_line(rh, score, x, y)

        return score

    # -------------------------------------------------
    # Render
    # -------------------------------------------------
    def render(self, reading, beat_filled=False):
        self.oled.oled.fill(0)

        score = self._draw_left_column(
            reading,
            x=self.indent_x,
            y=self.top_y,
            beat_filled=beat_filled
        )

        mood = self._mood_from_score(score)
        draw_face(
            self.oled.oled,
            self.oled.width,
            self.oled.height,
            mood,
            right_edge=True,
            fill_height_ratio=0.90
        )

        self.oled.oled.show()

    def show(self, reading):
        self.render(reading, beat_filled=False)

    # -------------------------------------------------
    # Live mode (1 second refresh, button-friendly)
    # -------------------------------------------------
    def show_live(self, get_reading, btn=None, refresh_ms=1000, max_seconds=0):
        start = time.ticks_ms()
        last_good = None
        beat = False

        while True:
            beat = not beat

            try:
                r = get_reading()
                if r is not None:
                    last_good = r
            except Exception:
                r = None

            self.render(r if r is not None else last_good, beat_filled=beat)

            wait_start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), wait_start) < int(refresh_ms):
                if btn is not None:
                    try:
                        if btn.poll_action():
                            return
                    except Exception:
                        pass
                time.sleep_ms(20)

            if max_seconds and max_seconds > 0:
                if time.ticks_diff(time.ticks_ms(), start) >= int(max_seconds * 1000):
                    return
