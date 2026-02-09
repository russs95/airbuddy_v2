# src/ui/glyphs.py — tiny pixel glyphs (Pico-safe, font-independent)

def draw_circle(fb, cx, cy, r=3, filled=False, color=1):
    """
    Draw a small circle on a framebuf-like object (supports pixel() and fill_rect()).
    r: 2..6 recommended
    """
    # Precomputed-ish offsets good for small radii
    pts = [
        (0, r), (1, r), (2, r-1), (3, r-2),
        (r, 0), (r, 1), (r-1, 2), (r-2, 3)
    ]

    # For r < 3, simplify
    if r < 3:
        pts = [(0, r), (r, 0), (1, r), (r, 1)]

    for dx, dy in pts:
        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            fb.pixel(cx + sx * dx, cy + sy * dy, color)
            fb.pixel(cx + sx * dy, cy + sy * dx, color)

    if filled:
        # Fill block size scales with radius
        # r=3 -> 3x3, r=4 -> 5x5, r=5 -> 5x5, r=6 -> 7x7
        if r <= 3:
            s = 3
        elif r <= 5:
            s = 5
        else:
            s = 7
        fb.fill_rect(cx - s//2, cy - s//2, s, s, color)


def draw_degree(fb, x, y, r=2, color=1):
    """
    Draw a tiny degree 'ring' symbol.
    x, y are TOP-LEFT of bounding box.
    """
    cx = x + r
    cy = y + r
    draw_circle(fb, cx, cy, r=r, filled=False, color=color)
