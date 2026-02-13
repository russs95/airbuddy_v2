# src/ui/faces.py — Reusable OLED face drawing (Pico / MicroPython safe)

def _in_bounds(w, h, x, y):
    return 0 <= x < w and 0 <= y < h


def _pix(fb, w, h, x, y, c=1):
    if _in_bounds(w, h, x, y):
        fb.pixel(x, y, c)


def _hline(fb, w, h, x, y, length, c=1):
    if y < 0 or y >= h:
        return
    x0 = max(0, x)
    x1 = min(w - 1, x + length - 1)
    for xx in range(x0, x1 + 1):
        fb.pixel(xx, y, c)


def _vline(fb, w, h, x, y, length, c=1):
    if x < 0 or x >= w:
        return
    y0 = max(0, y)
    y1 = min(h - 1, y + length - 1)
    for yy in range(y0, y1 + 1):
        fb.pixel(x, yy, c)


def _line(fb, w, h, x0, y0, x1, y1, c=1):
    # Bresenham
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _pix(fb, w, h, x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _thick_line(fb, w, h, x0, y0, x1, y1, thickness=2, c=1):
    _line(fb, w, h, x0, y0, x1, y1, c)
    if thickness <= 1:
        return
    _line(fb, w, h, x0 + 1, y0, x1 + 1, y1, c)
    _line(fb, w, h, x0 - 1, y0, x1 - 1, y1, c)
    _line(fb, w, h, x0, y0 + 1, x1, y1 + 1, c)
    _line(fb, w, h, x0, y0 - 1, x1, y1 - 1, c)


def _circle_outline(fb, w, h, cx, cy, r, c=1):
    x = r
    y = 0
    err = 0
    while x >= y:
        for dx, dy in (
                ( x,  y), ( y,  x), (-y,  x), (-x,  y),
                (-x, -y), (-y, -x), ( y, -x), ( x, -y)
        ):
            _pix(fb, w, h, cx + dx, cy + dy, c)
        y += 1
        err += 1 + 2 * y
        if 2 * (err - x) + 1 > 0:
            x -= 1
            err += 1 - 2 * x


def draw_thick_circle(fb, w, h, cx, cy, r, thickness=3, c=1):
    for i in range(thickness):
        rr = r - i
        if rr > 0:
            _circle_outline(fb, w, h, cx, cy, rr, c)


def _dot_eye(fb, w, h, cx, cy, size=3, c=1):
    s = max(1, size // 2)
    fb.fill_rect(cx - s, cy - s, 2 * s + 1, 2 * s + 1, c)


def _x_eye(fb, w, h, cx, cy, size=3, thick=2, c=1):
    s = size
    _thick_line(fb, w, h, cx - s, cy - s, cx + s, cy + s, thick, c)
    _thick_line(fb, w, h, cx - s, cy + s, cx + s, cy - s, thick, c)


def _star_eye(fb, w, h, cx, cy, size=3, thick=2, c=1):
    s = size
    _thick_line(fb, w, h, cx - s, cy, cx + s, cy, thick, c)
    _thick_line(fb, w, h, cx, cy - s, cx, cy + s, thick, c)
    _thick_line(fb, w, h, cx - s, cy - s, cx + s, cy + s, thick, c)
    _thick_line(fb, w, h, cx - s, cy + s, cx + s, cy - s, thick, c)


# ------------------------------------------------------------
# NEW: circular arc mouth (clean OLED look)
# ------------------------------------------------------------

def _mouth_arc(fb, w, h, cx, cy, radius, angle_span_deg=40, facing="up", thick=2, c=1):
    """
    Draw a short circular arc for a mouth.

    facing:
      - "up"   => smile (corners lower than middle)
      - "down" => frown (corners higher than middle)

    Uses shallow circular approximation.
    """

    radius = max(6, int(radius))

    # Increase span from ~30° to ~40°
    # Wider arc = larger half_span
    half_span = max(8, int(radius * 0.75))  # was ~0.55 before

    # Sagitta controls how deep the curve is
    sag = max(3, int(radius * 0.22))

    for dx in range(-half_span, half_span + 1):
        # Parabolic approximation of shallow circular segment
        y_off = int((dx * dx) * sag / max(1, (half_span * half_span)))

        if facing == "up":
            # Smile (∪): middle LOWEST (largest y) on screen
            yy = cy + sag - y_off
        else:
            # Frown (∩): middle HIGHEST (smallest y) on screen
            yy = cy - sag + y_off


        # Thickness
        for t in range(thick):
            _pix(fb, w, h, cx + dx, yy + t - (thick // 2), c)




def _mouth_flat(fb, w, h, cx, cy, w_half, thick=2, c=1):
    for t in range(thick):
        _hline(fb, w, h, cx - w_half, cy + t, w_half * 2 + 1, c)


def _mouth_worried(fb, w, h, cx, cy, w_half, thick=2, c=1):
    _thick_line(fb, w, h, cx - w_half, cy + 2, cx - 2, cy, thick, c)
    _thick_line(fb, w, h, cx - 2, cy, cx + w_half, cy + 1, thick, c)


def _mouth_frown_legacy(fb, w, h, cx, cy, w_half, curve, thick=2, c=1):
    # Keep for VERYBAD as requested
    for dx in range(-w_half, w_half + 1):
        y = int((dx * dx) / max(1, curve))
        yy = cy + y
        _pix(fb, w, h, cx + dx, yy, c)
        if thick >= 2:
            _pix(fb, w, h, cx + dx, yy - 1, c)
        if thick >= 3:
            _pix(fb, w, h, cx + dx, yy + 1, c)


def draw_face(fb, width, height, mood, *, right_edge=True, fill_height_ratio=0.90):
    r = int((height * float(fill_height_ratio)) / 2)
    r = max(10, min(r, (height // 2) - 2))

    cx = (width - 1) - r if right_edge else (width // 2)
    cy = height // 2

    draw_thick_circle(fb, width, height, cx, cy, r, thickness=3, c=1)

    eye_y = cy - int(r * 0.30)
    eye_dx = int(r * 0.35)
    mouth_y = cy + int(r * 0.32)

    lx = cx - eye_dx
    rx = cx + eye_dx

    eye_thick = 2
    mouth_thick = 2

    if mood == "star":
        _star_eye(fb, width, height, lx, eye_y, size=3, thick=eye_thick, c=1)
        _star_eye(fb, width, height, rx, eye_y, size=3, thick=eye_thick, c=1)
        # keep a smile arc for star too (looks great)
        _mouth_arc(fb, width, height, cx, mouth_y, radius=int(r * 0.55), facing="up", thick=3, c=1)

    elif mood == "good":
        _dot_eye(fb, width, height, lx, eye_y, size=3, c=1)
        _dot_eye(fb, width, height, rx, eye_y, size=3, c=1)
        _mouth_arc(fb, width, height, cx, mouth_y, radius=int(r * 0.50), facing="up", thick=mouth_thick, c=1)

    elif mood == "ok":
        _dot_eye(fb, width, height, lx, eye_y, size=3, c=1)
        _dot_eye(fb, width, height, rx, eye_y, size=3, c=1)
        _mouth_flat(fb, width, height, cx, mouth_y, w_half=int(r * 0.40), thick=mouth_thick, c=1)

    elif mood == "poor":
        _dot_eye(fb, width, height, lx, eye_y + 1, size=3, c=1)
        _dot_eye(fb, width, height, rx, eye_y + 1, size=3, c=1)
        _thick_line(fb, width, height, lx - 6, eye_y - 6, lx + 6, eye_y - 7, thickness=2, c=1)
        _thick_line(fb, width, height, rx - 6, eye_y - 7, rx + 6, eye_y - 6, thickness=2, c=1)
        _mouth_worried(fb, width, height, cx, mouth_y, w_half=int(r * 0.40), thick=mouth_thick, c=1)

    elif mood == "bad":
        _dot_eye(fb, width, height, lx, eye_y + 1, size=3, c=1)
        _dot_eye(fb, width, height, rx, eye_y + 1, size=3, c=1)
        _mouth_arc(fb, width, height, cx, mouth_y + 2, radius=int(r * 0.50), facing="down", thick=mouth_thick, c=1)

    else:  # "verybad" (KEEP frown as-is)
        _x_eye(fb, width, height, lx, eye_y, size=3, thick=eye_thick, c=1)
        _x_eye(fb, width, height, rx, eye_y, size=3, thick=eye_thick, c=1)
        _mouth_frown_legacy(
            fb, width, height, cx, mouth_y + 2,
            w_half=int(r * 0.40),
            curve=max(5, int(r * 0.25)),
            thick=mouth_thick,
            c=1
        )
        _thick_line(fb, width, height, cx - int(r * 0.55), cy + 2, cx - int(r * 0.35), cy + 8, thickness=2, c=1)
        _thick_line(fb, width, height, cx + int(r * 0.55), cy + 2, cx + int(r * 0.35), cy + 8, thickness=2, c=1)
