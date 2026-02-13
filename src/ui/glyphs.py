# src/ui/glyphs.py — tiny pixel glyphs for SSD1306/framebuf
# Pico / MicroPython safe

# ------------------------------------------------------------
# Low-level helpers
# ------------------------------------------------------------

def _pix(fb, x, y, c=1):
    try:
        fb.pixel(int(x), int(y), int(c))
    except Exception:
        pass


def _hline(fb, x, y, w, c=1):
    try:
        fb.hline(int(x), int(y), int(w), int(c))
    except Exception:
        # fallback
        for i in range(int(w)):
            _pix(fb, x + i, y, c)


def _vline(fb, x, y, h, c=1):
    try:
        fb.vline(int(x), int(y), int(h), int(c))
    except Exception:
        for i in range(int(h)):
            _pix(fb, x, y + i, c)


def _fill_rect(fb, x, y, w, h, c=1):
    try:
        fb.fill_rect(int(x), int(y), int(w), int(h), int(c))
    except Exception:
        for yy in range(int(h)):
            _hline(fb, x, y + yy, w, c)


def draw_bitmap_rows(fb, x, y, rows, c=1):
    """
    rows: list[str] of '0'/'1' where each string is a row of pixels.
    Top-left at (x, y).
    """
    x = int(x); y = int(y)
    for ry, row in enumerate(rows):
        for rx, ch in enumerate(row):
            if ch == "1":
                _pix(fb, x + rx, y + ry, c)


# ------------------------------------------------------------
# Degree ring (pixel)
# ------------------------------------------------------------

def draw_degree(fb, x, y, r=2, color=1):
    """
    Small hollow degree ring.
    (x, y) is top-left-ish anchor used in your screens.
    """
    x = int(x); y = int(y); r = int(r)
    cx = x + r
    cy = y + r

    # For r=2, a tight ring looks best with a 5x5 pattern
    # Generic small circle outline using symmetry
    pts = [
        (0, r), (1, r), (2, r-1),
        (r, 0), (r, 1), (r-1, 2),
    ]
    for dx, dy in pts:
        for sx, sy in ((1,1),(1,-1),(-1,1),(-1,-1)):
            _pix(fb, cx + sx*dx, cy + sy*dy, color)
            _pix(fb, cx + sx*dy, cy + sy*dx, color)


# ------------------------------------------------------------
# Circle (pixel) — used across screens
# ------------------------------------------------------------

def draw_circle(fb, cx, cy, r=4, filled=False, color=1):
    """
    Draws a small circle. If filled=True, draws a simple filled center.
    """
    cx = int(cx); cy = int(cy); r = int(r)

    # outline points (tuned for small r)
    pts = [
        (0, r), (1, r), (2, r-1), (3, r-2),
        (r, 0), (r, 1), (r-1, 2), (r-2, 3),
    ]
    for dx, dy in pts:
        for sx, sy in ((1,1),(1,-1),(-1,1),(-1,-1)):
            _pix(fb, cx + sx*dx, cy + sy*dy, color)
            _pix(fb, cx + sx*dy, cy + sy*dx, color)

    if filled:
        # simple fill for tiny circles
        _fill_rect(fb, cx-1, cy-1, 3, 3, color)


# ------------------------------------------------------------
# NEW: Pixel "C" glyph (for LARGE temp units)
# ------------------------------------------------------------

def draw_c(fb, x, y, scale=1, color=1):
    """
    Draw a pixel 'C' glyph. Works regardless of font coverage.
    Default is 7x9 at scale=1.
    """
    # 7x9 blocky C
    rows = [
        "0111110",
        "1100011",
        "1100000",
        "1100000",
        "1100000",
        "1100000",
        "1100011",
        "0111110",
        "0000000",
    ]

    # scale up by repeating pixels (simple nearest-neighbor)
    x = int(x); y = int(y); scale = max(1, int(scale))
    for ry, row in enumerate(rows):
        for rx, ch in enumerate(row):
            if ch == "1":
                _fill_rect(fb, x + rx*scale, y + ry*scale, scale, scale, color)


# ------------------------------------------------------------
# NEW: Subscript "2" glyph (₂) for CO₂ in MED
# ------------------------------------------------------------

def draw_sub2(fb, x, y, scale=1, color=1):
    """
    Draw a small subscript '2' glyph.
    Designed to sit slightly below baseline.
    Default size 4x5 (scale=1).
    """
    rows = [
        "1110",
        "0010",
        "1110",
        "1000",
        "1110",
    ]

    x = int(x); y = int(y); scale = max(1, int(scale))
    for ry, row in enumerate(rows):
        for rx, ch in enumerate(row):
            if ch == "1":
                _fill_rect(fb, x + rx*scale, y + ry*scale, scale, scale, color)


# ------------------------------------------------------------
# NEW: 9px-high face glyphs for thermo-bar labels
# Matches your screenshot style: eyes + mouth only, no circle.
# ------------------------------------------------------------

_FACE_9PX = {
    # 11x9 each (easy to read on SSD1306)
    # HAPPY
    "good": [
        "11000000011",
        "11000000011",
        "00000000000",
        "00000000000",
        "00100000100",
        "00010001000",
        "00001110000",
        "00000000000",
        "00000000000",
    ],
    # FLAT / OK
    "ok": [
        "11000000011",
        "11000000011",
        "00000000000",
        "00000000000",
        "00000000000",
        "00111111000",
        "00111111000",
        "00000000000",
        "00000000000",
    ],
    # WORRIED / POOR (small frown)
    "poor": [
        "11000000011",
        "11000000011",
        "00000000000",
        "00000000000",
        "00011111000",
        "00100000100",
        "01000000010",
        "00000000000",
        "00000000000",
    ],
    # SAD / BAD (deeper frown)
    "bad": [
        "11000000011",
        "11000000011",
        "00000000000",
        "00000000000",
        "01111111110",
        "01000000010",
        "00100000100",
        "00000000000",
        "00000000000",
    ],
    # VERY BAD (blocky "X" eyes + frown)
    "verybad": [
        "10100000101",
        "01000000010",
        "00000000000",
        "00000000000",
        "01111111110",
        "01000000010",
        "00100000100",
        "00000000000",
        "00000000000",
    ],
}


def draw_face9(fb, x, y, mood="ok", scale=1, color=1):
    """
    Draw one of the 9px face glyphs at (x, y).
    mood: "good", "ok", "poor", "bad", "verybad"
    """
    rows = _FACE_9PX.get(str(mood).lower(), _FACE_9PX["ok"])

    # scale by pixel replication
    x = int(x); y = int(y); scale = max(1, int(scale))
    for ry, row in enumerate(rows):
        for rx, ch in enumerate(row):
            if ch == "1":
                _fill_rect(fb, x + rx*scale, y + ry*scale, scale, scale, color)
