# src/ui/screens/co2.py
# CO₂ screen for AirBuddy
# Pico / MicroPython safe

from src.ui.thermobar import ThermoBar
from src.ui.glyphs import draw_sub2, draw_face9


class CO2Screen:
    """
    CO₂ (eCO2) screen (128x64)

    Health bar reference:
      400              1000        2000         5000
      :-)  OK  MEH  BAD  xx-(

    Confidence:
      - uses reading.confidence if present
      - if confidence_pct passed in, it overrides reading.confidence
      - if nothing available, shows "XX% CONF"
    """

    DISPLAY_DURATION = 4

    def __init__(self, oled):
        self.oled = oled

        # Fonts
        self.f_arvo = getattr(oled, "f_arvo", None)
        self.f_med = oled.f_med
        self.f_large = oled.f_large
        self.f_small = getattr(oled, "f_small", None)
        self.f_vs = oled.f_vsmall

        # Bar
        self.bar = ThermoBar(oled)

        # Scale labels above bar
        self.scale_ppm = [400, 1000, 2000, 5000]
        self.scale_x = [2, 40, 78, 108]  # tuned positions

        # Bottom labels
        self.left_face = "good"
        self.right_face = "verybad"

        # Layout tuning
        self.bar_x = 2
        self.bar_w = int(self.oled.width) - 4

        # Numbers + bar spacing
        self.scale_y = 34
        self.bar_y = 45  # lowered by 2px

        # 9px face glyph baseline
        self.faces_y = max(0, int(self.oled.height) - 9)

        _, h_vs = self.oled._text_size(self.f_vs, "Ag")
        self.labels_y = max(0, self.faces_y + 9 - h_vs)

        self.left_face_x = 2
        self.label_texts = ["OK", "MEH", "BAD"]
        self.label_x = [30, 56, 82]
        self.right_face_x = 110

        # Ticks at thresholds (we will align these to the label centers)
        self.tick_ppm = [400, 1000, 2000, 5000]

        self.tick_offset = {
            1000: 5,
            2000: -1,
            5000: -2,
        }


    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def show(self, reading, confidence_pct=None):
        self.oled.clear()

        ppm = int(getattr(reading, "eco2_ppm", 0))
        ready = bool(getattr(reading, "ready", True))

        # Confidence
        conf = None
        if confidence_pct is not None:
            try:
                conf = int(confidence_pct)
            except Exception:
                conf = None
        else:
            try:
                conf = int(getattr(reading, "confidence"))
            except Exception:
                conf = None

        if conf is None:
            conf_text = "XX%"
        else:
            if conf < 0:
                conf = 0
            if conf > 100:
                conf = 100
            conf_text = "{}%".format(conf)

        not_ready = (not ready) or (ppm <= 0)

        self._draw_header(ppm, conf_text, not_ready)
        self._draw_scale_numbers()
        self._draw_bar(ppm, not_ready)
        self._draw_fixed_ticks()
        self._draw_bottom_labels()

        self.oled.oled.show()

    # -------------------------------------------------
    # Drawing helpers
    # -------------------------------------------------
    def _draw_header(self, ppm, conf_text, not_ready):
        x0 = 2

        # Lower title by 2px
        y_title = 2

        # Lower CONF line by 5px (relative to previous)
        status_y = 19

        # Title: "eCO" + subscript 2 (Arvo if available else MED)
        title_writer = self.f_arvo if self.f_arvo else self.f_med

        # Faux-bold title for readability
        title_writer.write("eCO", x0, y_title)
        title_writer.write("eCO", x0 + 1, y_title)

        w_eco, _ = title_writer.size("eCO")
        sub2_x = x0 + int(w_eco) + 1
        sub2_y = y_title + 10
        draw_sub2(self.oled.oled, sub2_x, sub2_y, scale=1, color=1)

        # "PPM" in SMALL (fallback to VSMALL)
        ppm_writer = self.f_small if self.f_small else self.f_vs
        ppm_x = sub2_x + 6
        ppm_writer.write("PPM", ppm_x, y_title + (4 if ppm_writer is self.f_small else 5))

        # Status line
        if not_ready:
            self.f_med.write("SENSOR NOT READY", x0, status_y)
        else:
            conf_writer = self.f_small if self.f_small else self.f_vs
            conf_writer.write(conf_text, x0, status_y + (1 if conf_writer is self.f_small else 0))
            w_pct, _ = conf_writer.size(conf_text)
            conf_writer.write("CONF", x0 + int(w_pct) + 6, status_y + (1 if conf_writer is self.f_small else 0))

        # Value top-right, LARGE (only when ready)
        if not not_ready:
            val = str(int(ppm))
            tw, _ = self.f_large.size(val)
            x = int(self.oled.width) - int(tw) - 2
            y = 2
            self.f_large.write(val, x, y)

    def _draw_scale_numbers(self):
        # numbers above bar should be SMALL (fallback to VSMALL)
        writer = self.f_small if self.f_small else self.f_vs
        y = self.scale_y
        for ppm, x in zip(self.scale_ppm, self.scale_x):
            writer.write(str(ppm), int(x), int(y))

    def _ppm_to_step_p(self, ppm):
        edges = [400, 550, 700, 850, 1000, 1300, 1600, 2000, 2600, 3400, 5000]

        if ppm <= edges[0]:
            return 0.0
        if ppm >= edges[-1]:
            return 1.0

        for i in range(10):
            if edges[i] <= ppm < edges[i + 1]:
                return (i + 1) / 10.0

        return 1.0

    def _draw_bar(self, ppm, not_ready):
        p = 0.0 if not_ready else self._ppm_to_step_p(int(ppm))

        self.bar.draw(
            x=self.bar_x,
            y=self.bar_y,
            w=self.bar_w,
            p=p,
            outline=True,
            clear_bg=False
        )

        # Pointer at end of fill
        if not not_ready:
            x_end = self.bar_x + int(round(p * (self.bar_w - 1)))
            x_end = max(self.bar_x, min(self.bar_x + self.bar_w - 1, x_end))
            self.oled.oled.pixel(x_end, self.bar_y - 1, 1)

    def _inner_track_limits(self):
        # Must match ThermoBar._inner_geom() horizontal inset behavior
        inner_x = self.bar_x + 2
        inner_w = self.bar_w - 4
        if inner_w < 1:
            inner_w = 1
        return inner_x, inner_x + inner_w - 1

    def _tick_x_for_label_center(self, ppm):
        writer = self.f_small if self.f_small else self.f_vs

        try:
            i = self.scale_ppm.index(ppm)
            x_label = int(self.scale_x[i])
        except Exception:
            x_label = 0

        txt = str(ppm)
        tw, _ = writer.size(txt)
        x_center = x_label + (int(tw) // 2)

        # --- Apply optional manual offset ---
        x_center += self.tick_offset.get(ppm, 0)

        lo, hi = self._inner_track_limits()
        if x_center < lo:
            x_center = lo
        if x_center > hi:
            x_center = hi

        return x_center


    def _draw_tick(self, x):
        """
        Tick is 1px taller ABOVE the top border than before.
        Top border is at bar_y, so start at bar_y-2.
        """
        y0 = self.bar_y - 2
        for yy in range(6):  # 6px tall
            self.oled.oled.pixel(int(x), int(y0 + yy), 1)

    def _draw_fixed_ticks(self):
        for ppm in self.tick_ppm:
            x = self._tick_x_for_label_center(ppm)
            self._draw_tick(x)

    def _draw_bottom_labels(self):
        y_face = self.faces_y
        y_text = self.labels_y

        draw_face9(self.oled.oled, int(self.left_face_x), int(y_face), mood=self.left_face, scale=1, color=1)

        for txt, x in zip(self.label_texts, self.label_x):
            self.f_vs.write(txt, int(x), int(y_text))

        draw_face9(self.oled.oled, int(self.right_face_x), int(y_face), mood=self.right_face, scale=1, color=1)
