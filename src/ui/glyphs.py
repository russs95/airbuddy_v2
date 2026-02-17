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

    pts = [
        (0, r), (1, r), (2, r-1), (3, r-2),
        (r, 0), (r, 1), (r-1, 2), (r-2, 3),
    ]
    for dx, dy in pts:
        for sx, sy in ((1,1),(1,-1),(-1,1),(-1,-1)):
            _pix(fb, cx + sx*dx, cy + sy*dy, color)
            _pix(fb, cx + sx*dy, cy + sy*dx, color)

    if filled:
        _fill_rect(fb, cx-1, cy-1, 3, 3, color)


# ------------------------------------------------------------
# Pixel "C" glyph (for LARGE temp units)
# ------------------------------------------------------------

def draw_c(fb, x, y, scale=1, color=1):
    """
    Draw a pixel 'C' glyph. Default is 7x9 at scale=1.
    """
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

    x = int(x); y = int(y); scale = max(1, int(scale))
    for ry, row in enumerate(rows):
        for rx, ch in enumerate(row):
            if ch == "1":
                _fill_rect(fb, x + rx*scale, y + ry*scale, scale, scale, color)


# ------------------------------------------------------------
# Subscript "2" glyph (₂) for CO₂ in MED
# ------------------------------------------------------------

def draw_sub2(fb, x, y, scale=1, color=1):
    """
    Draw a small subscript '2' glyph. Default size 4x5 (scale=1).
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
# 9px-high face glyphs for thermo-bar labels (eyes + mouth only)
# ------------------------------------------------------------

_FACE_9PX = {
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

    x = int(x); y = int(y); scale = max(1, int(scale))
    for ry, row in enumerate(rows):
        for rx, ch in enumerate(row):
            if ch == "1":
                _fill_rect(fb, x + rx*scale, y + ry*scale, scale, scale, color)

# ------------------------------------------------------------
# NEW (REV): compact status indicators (6px high)
# - Smaller than 9px to reduce vertical crowding
# - Designed for top row use
# ------------------------------------------------------------

# ----------------------------
# WiFi indicator (9x6)
#   ON  = solid triangle with WIDE BASE AT BOTTOM (as requested)
#   OFF = hollow inverted pyramid (points DOWN)
# ----------------------------

# Original was appearing inverted in your UI, so we explicitly flip it vertically here.
_WIFI_ON_6 = [
    # wide base at bottom
    "111111111",
    "111111111",
    "011111110",
    "001111100",
    "000111000",
    "000010000",
]

_WIFI_OFF_6 = [
    # hollow down triangle outline
    "111111111",
    "100000001",
    "010000010",
    "001000100",
    "000101000",
    "000010000",
]

def draw_wifi(fb, x, y, on=True, color=1):
    """
    Draw compact WiFi indicator at (x, y). Size: 9x6.
    - on=True  => solid triangle, wide base at bottom
    - on=False => hollow inverted pyramid outline (points DOWN)
    """
    rows = _WIFI_ON_6 if bool(on) else _WIFI_OFF_6
    draw_bitmap_rows(fb, x, y, rows, c=color)

# Backward compatible alias (if older code calls draw_wifi9)
def draw_wifi9(fb, x, y, on=True, color=1):
    draw_wifi(fb, x, y, on=on, color=color)


# ----------------------------
# GPS indicator (14x6) — blocky "GPS"
# Horizontal/vertical strokes only.
# ----------------------------

_GPS_6 = [
    # G(4) 0 P(4) 0 S(4) => 14 columns
    "1111" "0" "1110" "0" "1111",
    "1000" "0" "1001" "0" "1000",
    "1011" "0" "1110" "0" "1111",
    "1001" "0" "1000" "0" "0001",
    "1001" "0" "1000" "0" "0001",
    "1111" "0" "1000" "0" "1111",
]

def draw_gps(fb, x, y, color=1):
    """
    Draw compact 6px-high 'GPS' at (x, y). Size: 14x6.
    """
    draw_bitmap_rows(fb, x, y, _GPS_6, c=color)

# Backward compatible alias
def draw_gps9(fb, x, y, color=1):
    draw_gps(fb, x, y, color=color)


# ----------------------------
# API indicator (7x7) — dedicated glyph (ONE ROW TALLER)
#   ON  = hollow ring with center dot
#   OFF = hollow ring only
# Height now matches others visually better.
# ----------------------------

_API_ON_7 = [
    "0011100",
    "0100010",
    "1000001",
    "1001001",  # center dot pair
    "1000001",
    "0100010",
    "0011100",
]

_API_OFF_7 = [
    "0011100",
    "0100010",
    "1000001",
    "1000001",
    "1000001",
    "0100010",
    "0011100",
]

def draw_api(fb, x, y, on=True, color=1):
    """
    Draw compact API indicator at (x, y). Size: 7x7.
    - on=True  => ring + dot
    - on=False => ring only (hollow)
    """
    rows = _API_ON_7 if bool(on) else _API_OFF_7
    draw_bitmap_rows(fb, x, y, rows, c=color)

