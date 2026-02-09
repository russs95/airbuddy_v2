# src/ui/screens/tvoc.py
# TVOC screen for AirBuddy
# Pico / MicroPython safe

from src.ui.thermobar import ThermoBar


class TVOCScreen:
    """
    TVOC (ppb) screen (128x64), matching CO2Screen layout.

    Top left:
      - "TVOC" (MED, faux-bold)
      - "PPB" (SMALL/VSMALL)
      - Status line: "<conf>% CONF" or "SENSOR NOT READY"

    Top right:
      - TVOC value (LARGE, right aligned) when ready
      - When NOT ready: no value shown

    Bottom:
      - Scale numbers above bar (VSMALL)
      - ThermoBar filled in 10 discrete steps
      - Qualitative labels below bar (VSMALL)
    """

    DISPLAY_DURATION = 4  # seconds

    def __init__(self, oled):
        self.oled = oled

        # Fonts
        self.f_med = oled.f_med
        self.f_large = oled.f_large
        self.f_small = getattr(oled, "f_small", None)
        self.f_vs = oled.f_vsmall

        # Bar
        self.bar = ThermoBar(oled)

        # ----------------------------
        # Scale numbers above bar (ppb)
        # ----------------------------
        # Breakpoints (approx common guidance):
        # 0-220 good, 220-660 ok, 660-2200 poor, 2200-5500 bad/hazard
        self.scale_ppb = [0, 220, 660, 2200, 5500]
        self.scale_x = [2, 30, 54, 86, 108]  # tuned for 128px

        # ----------------------------
        # Qualitative labels below bar
        # ----------------------------
        self.labels = ["GOOD", "OK", "POOR", "BAD", "!!!"]
        self.label_x = [2, 36, 60, 88, 112]

        # Layout
        self.bar_x = 2
        self.bar_w = int(self.oled.width) - 4

        self.scale_y = 35
        self.bar_y = 43
        self.labels_y = max(0, int(self.oled.height) - 10)

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def show(self, reading, confidence_pct=None):
        """
        reading.tvoc_ppb required (but may be 0 when not ready)
        reading.ready (bool) optional
        reading.confidence optional (preferred)
        confidence_pct: optional override (int 0..100)
        """
        self.oled.clear()

        tvoc = int(getattr(reading, "tvoc_ppb", 0))
        ready = bool(getattr(reading, "ready", True))

        # Confidence (same pattern as CO2 screen)
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
            conf = 0 if conf < 0 else 100 if conf > 100 else conf
            conf_text = "{}%".format(conf)

        not_ready = (not ready) or (tvoc <= 0)

        self._draw_header(tvoc, conf_text, not_ready)
        self._draw_scale_numbers()
        self._draw_bar(tvoc, not_ready)
        self._draw_labels()

        self.oled.oled.show()

    # -------------------------------------------------
    # Drawing helpers
    # -------------------------------------------------
    def _draw_header(self, tvoc, conf_text, not_ready):
        x0 = 2
        y0 = 0

        # Faux-bold "TVOC"
        self.f_med.write("TVOC", x0, y0)
        self.f_med.write("TVOC", x0 + 1, y0)

        # "PPB" in SMALL (fallback to VSMALL)
        w_main, _ = self.f_med.size("TVOC")
        unit_writer = self.f_small if self.f_small else self.f_vs
        unit_writer.write("PPB", x0 + int(w_main) + 6, y0 + (4 if unit_writer is self.f_small else 5))

        status_y = 14
        if not_ready:
            self.f_med.write("SENSOR NOT READY", x0, status_y)
        else:
            self.f_med.write(conf_text, x0, status_y)
            conf_writer = self.f_small if self.f_small else self.f_vs
            w_pct, _ = self.f_med.size(conf_text)
            conf_writer.write("CONF", x0 + int(w_pct) + 6, status_y + (2 if conf_writer is self.f_small else 3))

        # Value top-right, LARGE (only when ready)
        if not not_ready:
            val = str(int(tvoc))
            tw, _ = self.f_large.size(val)
            x = int(self.oled.width) - int(tw) - 2
            y = 2
            self.f_large.write(val, x, y)

    def _draw_scale_numbers(self):
        y = self.scale_y
        for v, x in zip(self.scale_ppb, self.scale_x):
            self.f_vs.write(str(v), int(x), int(y))

    def _tvoc_to_step_p(self, tvoc):
        """
        Convert TVOC ppb to 10-step bar fill.
        We use 0..5500 mapping and quantize to tenths.
        """
        if tvoc <= 0:
            return 0.0
        if tvoc >= 5500:
            return 1.0

        p_raw = tvoc / 5500.0
        # quantize to 10 steps
        step = int(p_raw * 10 + 0.999)  # ceil-ish so small values show something
        if step < 0:
            step = 0
        if step > 10:
            step = 10
        return step / 10.0

    def _draw_bar(self, tvoc, not_ready):
        p = 0.0 if not_ready else self._tvoc_to_step_p(int(tvoc))
        self.bar.draw(
            x=self.bar_x,
            y=self.bar_y,
            w=self.bar_w,
            p=p,
            outline=True,
            clear_bg=False
        )

    def _draw_labels(self):
        y = self.labels_y
        for label, x in zip(self.labels, self.label_x):
            self.f_vs.write(label, int(x), int(y))
