# src/ui/connection_header.py
#
# Consolidated connectivity status header: GPS  API  WiFi
#
# Draws a right-aligned cluster of three icons at the top of any screen.
# Import and call draw() from any screen that needs the connectivity row.
#
# GPS states (re-exported for callers):
#   GPS_NONE  (0) — no hardware / disabled        → outline triangle
#   GPS_INIT  (1) — hardware present, no fix       → partially filled triangle
#   GPS_FIXED (2) — has satellite fix              → fully filled triangle
#
# Live probing
# ------------
# WiFi:  draw() always probes network.WLAN live — a fast C-level flag read,
#        no socket or I/O.  The wifi_ok parameter is accepted for backward
#        compatibility but is no longer used; the live result always wins.
#
# API:   HTTP cannot be performed inside a draw call.  Instead a module-level
#        boolean _api_ok is maintained.  Call set_api_ok(True/False) from the
#        telemetry scheduler after each POST attempt.  draw() uses that cached
#        value when the caller passes api_connected=None (the default).
#        Callers that pass an explicit True/False still override the cache for
#        that call (and update the cache so later draw() calls stay in sync).

from src.ui.glyphs import draw_wifi, draw_gps, draw_api
from src.ui.glyphs import GPS_NONE, GPS_INIT, GPS_FIXED  # noqa: F401 — re-exported

# Icon pixel dimensions (callers may import for layout math)
WIFI_W = 9
WIFI_H = 6
API_W  = 7
API_H  = 6
GPS_W  = 14
GPS_H  = 6
HEIGHT = 6   # height of the header strip

# ---------------------------------------------------------------------------
# Module-level API reachability cache.
# Updated by set_api_ok(); persists across draw() calls.
# ---------------------------------------------------------------------------
_api_ok = False


def set_api_ok(ok):
    """
    Update the cached API reachability flag.
    Call this from the telemetry scheduler after each POST attempt so that
    every screen's connection header reflects the actual server state.
    """
    global _api_ok
    _api_ok = bool(ok)


def _probe_wifi():
    """
    Live WiFi check via MicroPython network module.
    Reads a C-level flag — no socket or I/O overhead (~0.1 ms).
    Returns False on Pico without WiFi hardware, import error, etc.
    """
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        return bool(wlan.active() and wlan.isconnected())
    except Exception:
        return False


def draw(
        fb,
        oled_width,
        gps_state=GPS_NONE,
        api_connected=None,
        wifi_ok=None,        # accepted for compat; live probe is always used instead
        api_sending=False,
        now_ms=None,
        icon_y=1,
        right_inset=1,
        gap=4,
):
    """
    Draw the right-aligned GPS / API / WiFi status cluster.

    Cluster layout (right-to-left): WiFi — gap — API — gap — GPS

    Parameters
    ----------
    fb            : framebuf / SSD1306 framebuffer
    oled_width    : screen width in pixels
    gps_state     : GPS_NONE (0), GPS_INIT (1), or GPS_FIXED (2)
    api_connected : True/False to override the module cache, or None to use it
    wifi_ok       : deprecated — live probe is always used; ignored
    api_sending   : True during an active telemetry send pulse
    now_ms        : current time.ticks_ms() value, or None to sample internally
    icon_y        : top-y pixel of the icon row
    right_inset   : pixels inset from right edge before the first icon
    gap           : pixels between icons
    """
    # WiFi: always probe live.
    wifi_actual = _probe_wifi()

    # API: use the caller-supplied value if explicit; fall back to cache.
    # The cache is only updated via set_api_ok() — passing an explicit value
    # here is a local display decision and must NOT overwrite the cache.
    if api_connected is None:
        api_actual = _api_ok
    else:
        api_actual = bool(api_connected)

    w = int(oled_width)
    y = int(icon_y)
    g = int(gap)
    x = w - int(right_inset)

    # WiFi (rightmost)
    x -= WIFI_W
    fb.fill_rect(x, y, WIFI_W, WIFI_H, 0)
    draw_wifi(fb, x, y, on=wifi_actual, color=1)
    x -= g

    # API
    x -= API_W
    fb.fill_rect(x, y, API_W, API_H, 0)
    draw_api(
        fb, x, y,
        on=bool(api_actual),
        heartbeat=bool(api_actual),
        sending=bool(api_sending),
        color=1,
        now_ms=now_ms,
    )
    x -= g

    # GPS (leftmost in cluster)
    x -= GPS_W
    fb.fill_rect(x, y, GPS_W, GPS_H, 0)
    draw_gps(fb, x, y, state=int(gps_state), color=1)
