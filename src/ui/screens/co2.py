# src/ui/screens/co2.py
# CO₂ screen for AirBuddy
# Pico / MicroPython safe

from src.ui.thermobar import ThermoBar


class CO2Screen:
    """
    CO₂ (eCO2) screen (128x64)

    Top left:
      - "eCO2" (MED, faux-bold)
      - "PPM" (SMALL)
      - Status line: either "92% CONF" or "SENSOR NOT READY"

    Top right:
      - CO2 value (LARGE, right aligned) when ready
      - When NOT ready: no value shown (gives space for status)

    Bottom:
      - Scale numbers above bar (VSMALL)
      - ThermoBar (tight placement)
      - Qualitative labels below bar (VSMALL, bottom-aligned, tighter gap)
    """

    DISPLAY_DURATION = 10  # seconds (main.py should use this)

    def __init__(self, oled):
        self.oled = oled

        # Fonts
        self.f_med = oled.f_med
        self.f_large = oled.f_large
        self.f_small = getattr(oled, "f_small", None)  # for PPM + CONF
        self.f_vs = oled.f_vsmall

        # Bar
        self.bar = ThermoBar(oled)

        # CO₂ scale reference points (ppm) + x positions
        self.scale_ppm = [400, 800, 1200]
        self.scale_x = [10, 54, 98]

        # Qualitative labels (CAPS for consistent height)
        self.labels = ["GOOD", "OK", "MEH", "BAD"]
        self.label_x = [10, 44, 74, 102]

        # Layout tuning
        self.bar_x = 8
        self.bar_w = int(self.oled.width) - 16

        # Tight bottom block
        self.scale_y = 35                 # numbers above bar
        self.bar_y = 43                   # bar
        self.labels_y = int(self.oled.height) - 8
        self.labels_y = max(0, self.labels_y - 2)  # tighten gap under bar

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def show(self, reading, confidence_pct=None):
        """
        reading.eco2_ppm required (but may be 0 when not ready)
        reading.ready (bool) optional
        reading.confidence optional (preferred)
        confidence_pct: optional override (int 0..100). If override is provided, use it.
        """
        self.oled.clear()

        ppm = int(getattr(reading, "eco2_ppm", 0))
        ready = bool(getattr(reading, "ready", True))

        # Prefer live confidence from reading unless an override is provided
        conf = None
        if confidence_pct is not None:
            try:
                conf = int(confidence_pct)
            except Exception:
                conf = None
        else:
            # reading.confidence might be missing or invalid
            try:
                conf = int(getattr(reading, "confidence"))
            except Exception:
                conf = None

        # If confidence is missing/failed, display "XX%" so you can spot it
        conf_text = None
        if conf is None:
            conf_text = "XX%"
        else:
            # Clamp
            if conf < 0:
                conf = 0
            elif conf > 100:
                conf = 100
            conf_text = "{}%".format(conf)

        # Not-ready rule: either explicit ready==False OR ppm <= 0
        not_ready = (not ready) or (ppm <= 0)

        self._draw_header(ppm, conf_text, not_ready)
        self._draw_scale_numbers()
        self._draw_bar(ppm, not_ready)
        self._draw_labels()

        self.oled.oled.show()

    # -------------------------------------------------
    # Drawing helpers
    # -------------------------------------------------
    def _draw_header(self, ppm, conf_text, not_ready):
        x0 = 2
        y0 = 0

        # Faux-bold "eCO2"
        self.f_med.write("eCO2", x0, y0)
        self.f_med.write("eCO2", x0 + 1, y0)

        # "PPM" in SMALL (fallback to VSMALL if small not available)
        w_main, _ = self.f_med.size("eCO2")
        ppm_writer = self.f_small if self.f_small else self.f_vs
        ppm_writer.write("PPM", x0 + int(w_main) + 6, y0 + (4 if ppm_writer is self.f_small else 5))

        # Status line below title
        status_y = 14
        if not_ready:
            # Use the full horizontal space
            self.f_med.write("SENSOR NOT READY", x0, status_y)
        else:
            # "92% CONF" where CONF is SMALL
            self.f_med.write(conf_text, x0, status_y)

            # CONF in SMALL (fallback to VSMALL)
            conf_writer = self.f_small if self.f_small else self.f_vs
            w_pct, _ = self.f_med.size(conf_text)
            conf_writer.write("CONF", x0 + int(w_pct) + 6, status_y + (2 if conf_writer is self.f_small else 3))

        # Value top-right, LARGE (only when ready)
        if not not_ready:
            val = str(int(ppm))
            tw, _ = self.f_large.size(val)
            x = int(self.oled.width) - int(tw) - 2
            y = 2
            self.f_large.write(val, x, y)

    def _draw_scale_numbers(self):
        y = self.scale_y
        for ppm, x in zip(self.scale_ppm, self.scale_x):
            self.f_vs.write(str(ppm), int(x), int(y))

    def _ppm_to_p(self, ppm):
        # 400..2000 maps to 0..1
        if ppm <= 400:
            return 0.0
        if ppm >= 2000:
            return 1.0
        return (ppm - 400) / 1600.0

    def _draw_bar(self, ppm, not_ready):
        p = 0.0 if not_ready else self._ppm_to_p(int(ppm))
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
