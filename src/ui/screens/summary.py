# src/ui/screens/summary.py — Summary screen (Pico / MicroPython safe)

from src.ui.glyphs import draw_degree


class SummaryScreen:
    """
    Summary screen:

    Left column (SMALL):
      29°C       (degree ring drawn in pixels + C)
      78%
      440 CO2
      1200 ppb

    Right side:
      Large drawn face in a circle:
        🤩 (CO2 < 400)
        🙂 good
        😐 ok
        😕 poor
        🙁 bad
        😫 very bad
    """

    def __init__(self, oled):
        self.oled = oled

    # -------------------------------------------------
    # Classification
    # -------------------------------------------------
    def _mood_from_reading(self, r):
        """
        Returns mood key:
          "star", "good", "ok", "poor", "bad", "verybad"
        Uses CO2 as primary, TVOC can bump worse by 1 level.
        """
        ppm = int(getattr(r, "eco2_ppm", 0) or 0)
        tvoc = int(getattr(r, "tvoc_ppb", 0) or 0)
        ready = bool(getattr(r, "ready", True))

        if (not ready) or (ppm <= 0):
            # if not ready, show worried (better than lying)
            return "poor"

        # CO2 tiers (you can tweak anytime)
        if ppm < 400:
            base = 0  # star
        elif ppm < 800:
            base = 1  # good
        elif ppm < 1200:
            base = 2  # ok
        elif ppm < 2000:
            base = 3  # poor
        elif ppm < 5000:
            base = 4  # bad
        else:
            base = 5  # verybad

        # TVOC bump rule (simple, effective)
        # 0-220 good, 220-660 ok, 660-2200 poor, >2200 bad
        bump = 0
        if tvoc > 2200:
            bump = 2
        elif tvoc > 660:
            bump = 1

        level = base + bump

        # map to mood key
        if level <= 0:
            return "star"
        if level == 1:
            return "good"
        if level == 2:
            return "ok"
        if level == 3:
            return "poor"
        if level == 4:
            return "bad"
        return "verybad"

    # -------------------------------------------------
    # Left column text
    # -------------------------------------------------
    def _draw_temp_line(self, temp_c, x, y):
        """
        Draw like: 29°C (degree ring pixel + C) using SMALL font.
        """
        if temp_c is None:
            self.oled.f_small.write("--", x, y)
            return

        try:
            t = int(round(float(temp_c)))
        except Exception:
            self.oled.f_small.write("--", x, y)
            return

        num = str(t)

        w_num, _ = self.oled._text_size(self.oled.f_small, num)
        w_c, _ = self.oled._text_size(self.oled.f_small, "C")

        deg_r = 2
        deg_w = deg_r * 2 + 1  # ~5px

        # number
        self.oled.f_small.write(num, x, y)

        # degree ring
        x_deg = x + w_num + 1
        y_deg = y + 2
        draw_degree(self.oled.oled, x_deg, y_deg, r=deg_r, color=1)

        # C
        x_c = x_deg + deg_w + 1
        self.oled.f_small.write("C", x_c, y)

    def _draw_left_column(self, r, x=2, y=2, line_h=14):
        temp_c = getattr(r, "temp_c", None) if r else None
        rh = getattr(r, "humidity", None) if r else None
        eco2 = getattr(r, "eco2_ppm", None) if r else None
        tvoc = getattr(r, "tvoc_ppb", None) if r else None

        # 1) Temp
        self._draw_temp_line(temp_c, x, y)
        y += line_h

        # 2) RH
        if rh is not None:
            try:
                rh_i = int(round(float(rh)))
                self.oled.f_small.write(str(rh_i) + "%", x, y)
            except Exception:
                self.oled.f_small.write("--%", x, y)
        else:
            self.oled.f_small.write("--%", x, y)
        y += line_h

        # 3) CO2
        if eco2 is not None:
            try:
                self.oled.f_small.write(str(int(eco2)) + " CO2", x, y)
            except Exception:
                self.oled.f_small.write("-- CO2", x, y)
        else:
            self.oled.f_small.write("-- CO2", x, y)
        y += line_h

        # 4) TVOC
        if tvoc is not None:
            try:
                self.oled.f_small.write(str(int(tvoc)) + " ppb", x, y)
            except Exception:
                self.oled.f_small.write("-- ppb", x, y)
        else:
            self.oled.f_small.write("-- ppb", x, y)

    # -------------------------------------------------
    # Face drawing primitives
    # -------------------------------------------------
    def _circle_outline(self, cx, cy, r):
        """
        Midpoint-ish circle outline.
        """
        x = r
        y = 0
        err = 0

        while x >= y:
            for dx, dy in (
                    ( x,  y), ( y,  x), (-y,  x), (-x,  y),
                    (-x, -y), (-y, -x), ( y, -x), ( x, -y)
            ):
                px = cx + dx
                py = cy + dy
                if 0 <= px < self.oled.width and 0 <= py < self.oled.height:
                    self.oled.oled.pixel(px, py, 1)

            y += 1
            err += 1 + 2*y
            if 2*(err - x) + 1 > 0:
                x -= 1
                err += 1 - 2*x

    def _line(self, x0, y0, x1, y1):
        """
        Simple Bresenham line.
        """
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        while True:
            if 0 <= x0 < self.oled.width and 0 <= y0 < self.oled.height:
                self.oled.oled.pixel(x0, y0, 1)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def _star_eye(self, cx, cy, size=3):
        """
        Star-like eye: plus + X overlay.
        """
        s = size
        self._line(cx - s, cy, cx + s, cy)
        self._line(cx, cy - s, cx, cy + s)
        self._line(cx - s, cy - s, cx + s, cy + s)
        self._line(cx - s, cy + s, cx + s, cy - s)

    def _x_eye(self, cx, cy, size=3):
        s = size
        self._line(cx - s, cy - s, cx + s, cy + s)
        self._line(cx - s, cy + s, cx + s, cy - s)

    def _dot_eye(self, cx, cy):
        self.oled.oled.fill_rect(cx - 1, cy - 1, 3, 3, 1)

    def _mouth_smile(self, cx, cy, w, h):
        """
        Curved smile using a parabola.
        """
        for dx in range(-w, w + 1):
            y = int((dx * dx) / max(1, h))
            self.oled.oled.pixel(cx + dx, cy + y, 1)

    def _mouth_frown(self, cx, cy, w, h):
        for dx in range(-w, w + 1):
            y = int((dx * dx) / max(1, h))
            self.oled.oled.pixel(cx + dx, cy - y, 1)

    def _mouth_flat(self, cx, cy, w):
        self.oled.oled.hline(cx - w, cy, w * 2, 1)

    def _mouth_worried(self, cx, cy, w):
        """
        A slight angled / kink mouth: \_
        """
        self._line(cx - w, cy + 2, cx - 2, cy)     # left upstroke
        self._line(cx - 2, cy, cx + w, cy + 1)     # right shallow downstroke

    # -------------------------------------------------
    # Big face
    # -------------------------------------------------
    def _draw_face(self, mood):
        """
        Draw the big circle face on the right.
        Right edge touches OLED edge; ~90% height.
        """
        r = 29  # ~90% of 64px height (diameter ~58)
        cx = (self.oled.width - 1) - r
        cy = self.oled.height // 2

        # Outline circle
        self._circle_outline(cx, cy, r)

        # Face feature positions
        eye_y = cy - 10
        eye_dx = 10
        mouth_y = cy + 10

        left_eye_x = cx - eye_dx
        right_eye_x = cx + eye_dx

        if mood == "star":
            self._star_eye(left_eye_x, eye_y, size=3)
            self._star_eye(right_eye_x, eye_y, size=3)
            self._mouth_smile(cx, mouth_y, w=12, h=10)
            # extra "big smile" thickness
            self._mouth_smile(cx, mouth_y + 1, w=12, h=10)

        elif mood == "good":
            self._dot_eye(left_eye_x, eye_y)
            self._dot_eye(right_eye_x, eye_y)
            self._mouth_smile(cx, mouth_y, w=11, h=11)

        elif mood == "ok":
            self._dot_eye(left_eye_x, eye_y)
            self._dot_eye(right_eye_x, eye_y)
            self._mouth_flat(cx, mouth_y + 2, w=12)

        elif mood == "poor":
            # worried: slightly raised brows (tiny lines) + worried mouth
            self._dot_eye(left_eye_x, eye_y + 1)
            self._dot_eye(right_eye_x, eye_y + 1)
            self._line(left_eye_x - 4, eye_y - 5, left_eye_x + 4, eye_y - 6)
            self._line(right_eye_x - 4, eye_y - 6, right_eye_x + 4, eye_y - 5)
            self._mouth_worried(cx, mouth_y + 2, w=12)

        elif mood == "bad":
            self._dot_eye(left_eye_x, eye_y + 1)
            self._dot_eye(right_eye_x, eye_y + 1)
            self._mouth_frown(cx, mouth_y + 2, w=12, h=10)

        else:  # "verybad"
            self._x_eye(left_eye_x, eye_y, size=3)
            self._x_eye(right_eye_x, eye_y, size=3)
            self._mouth_frown(cx, mouth_y + 2, w=12, h=8)
            # extra stress marks
            self._line(cx - 16, cy + 2, cx - 10, cy + 6)
            self._line(cx + 16, cy + 2, cx + 10, cy + 6)

    # -------------------------------------------------
    # Public
    # -------------------------------------------------
    def show(self, reading):
        self.oled.oled.fill(0)

        # Left column
        self._draw_left_column(reading, x=2, y=6, line_h=14)

        # Face
        mood = self._mood_from_reading(reading)
        self._draw_face(mood)

        self.oled.oled.show()
