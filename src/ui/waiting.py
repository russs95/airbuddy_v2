# src/ui/waiting.py  (MicroPython / Pico-safe)
#
# Waiting / idle screen renderer + holder:
#   - airBuddy logo (bitmap module)
#   - tagline text (MED font)
#   - optional animated dots (base, base., base.., base...), 1 step per second
#   - status icons (top-right), ORDER: GPS  API  WIFI
#
# New:
#   - show_live(...): holds on waiting screen until a click action occurs
#   - API heartbeat animation when api_ok=True (double-beat)
#     * Offline  => empty ring
#     * Online   => SOLID ring (default)
#     * Heartbeat alternates empty <-> solid in a double-beat pattern
#
# Click safety:
#   - Never blocks longer than poll_ms
#   - Only redraws the tiny icon region on heartbeat ticks (no full-screen redraw)
#   - Optional dotted-line text animation remains off by default (animate=False)

import time
import gc
from src.ui import logo_airbuddy
from src.ui.glyphs import draw_wifi, draw_gps, draw_api


class WaitingScreen:
    def __init__(self, flip_x=False, flip_y=True, gap=6, logo_drop_px=10):
        self.flip_x = flip_x
        self.flip_y = flip_y

        self.gap = int(gap)
        self.logo_drop_px = int(logo_drop_px)

        # timeline
        self._start_ms = None

        # logo cache
        self._logo_lw = None
        self._logo_lh = None
        self._logo_data = None

        # UI tweaks
        self.logo_y_offset_px = -2
        self.line_y_offset_px = -6

        self.cluster_right_inset_px = 1
        self.icon_gap_px = 4
        self.icon_y = 1

        # ----------------------------
        # Heartbeat animation params
        # ----------------------------
        # Double-beat pattern over 900ms:
        #   beat1 80ms, gap 120ms, beat2 70ms, rest...
        self._hb_cycle_ms = 900
        self._hb_b1_ms = 80
        self._hb_gap_ms = 120
        self._hb_b2_ms = 70

        # redraw only icons row every N ms when api_ok=True
        self._hb_icon_redraw_every_ms = 50
        self._hb_next_icon_redraw_ms = 0

        # cache the last heartbeat state so we avoid redundant redraws
        self._last_api_state = None  # tuple(api_ok, api_draw_mode)

    # ----------------------------
    # PUBLIC API (render once)
    # ----------------------------
    def show(
            self,
            oled,
            line="Know your air...",
            animate=False,
            period_ms=1000,
            *,
            wifi_ok=False,
            gps_on=False,
            api_ok=False
    ):
        self.render(
            oled,
            line=line,
            animate=animate,
            period_ms=period_ms,
            wifi_ok=wifi_ok,
            gps_on=gps_on,
            api_ok=api_ok
        )

    # ----------------------------
    # PUBLIC API (HOLD until click)
    # ----------------------------
    def show_live(
            self,
            oled,
            btn,
            line="Know your air...",
            animate=False,
            period_ms=1000,
            *,
            wifi_ok=False,
            gps_on=False,
            api_ok=False,
            poll_ms=25,
            flush_ms=350
    ):
        """
        Draw waiting screen and HOLD until a button action occurs.

        Returns:
          action string from btn.poll_action(), e.g. "single", "double", "triple", "quad", "debug".
        """
        # Full render once
        self.render(
            oled,
            line=line,
            animate=animate,
            period_ms=period_ms,
            wifi_ok=wifi_ok,
            gps_on=gps_on,
            api_ok=api_ok
        )

        if btn is None:
            return None

        # reset click state
        try:
            btn.reset()
        except Exception:
            pass

        # flush stale click detections right after boot
        try:
            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < int(flush_ms):
                try:
                    btn.poll_action()  # discard
                except Exception:
                    pass
                time.sleep_ms(int(poll_ms))
        except Exception:
            pass

        # seed icon redraw schedule
        try:
            now = self._now_ms()
            self._hb_next_icon_redraw_ms = time.ticks_add(now, self._hb_icon_redraw_every_ms)
        except Exception:
            self._hb_next_icon_redraw_ms = 0

        # loop
        while True:
            now = self._now_ms()

            # optional dotted text animation (OFF by default; expensive full render)
            if animate:
                self.render(
                    oled,
                    line=line,
                    animate=True,
                    period_ms=period_ms,
                    wifi_ok=wifi_ok,
                    gps_on=gps_on,
                    api_ok=api_ok
                )
                # reset icon schedule after full redraw
                try:
                    self._hb_next_icon_redraw_ms = time.ticks_add(now, self._hb_icon_redraw_every_ms)
                except Exception:
                    pass
                self._last_api_state = None

            # heartbeat: only redraw icon cluster
            if api_ok:
                try:
                    if time.ticks_diff(now, self._hb_next_icon_redraw_ms) >= 0:
                        api_mode = self._api_draw_mode(now, api_ok=api_ok)

                        # avoid redundant redraws
                        st = (bool(api_ok), int(api_mode))
                        if st != self._last_api_state:
                            self._draw_status_icons(
                                oled,
                                wifi_ok=wifi_ok,
                                gps_on=gps_on,
                                api_ok=api_ok,
                                api_mode=api_mode
                            )
                            fb = getattr(oled, "oled", None)
                            if fb:
                                fb.show()
                            self._last_api_state = st

                        self._hb_next_icon_redraw_ms = time.ticks_add(now, self._hb_icon_redraw_every_ms)
                except Exception:
                    pass
            else:
                # offline: ensure we show "empty ring" once
                st = (False, 0)
                if st != self._last_api_state:
                    self._draw_status_icons(
                        oled,
                        wifi_ok=wifi_ok,
                        gps_on=gps_on,
                        api_ok=False,
                        api_mode=0
                    )
                    fb = getattr(oled, "oled", None)
                    if fb:
                        fb.show()
                    self._last_api_state = st

            # poll button
            try:
                action = btn.poll_action()
            except Exception:
                action = None

            if action is not None:
                return action

            time.sleep_ms(int(poll_ms))

    # ----------------------------
    # Logo cache + pixel blit
    # ----------------------------
    def _get_logo_cached(self):
        if self._logo_lw is not None:
            return self._logo_lw, self._logo_lh, self._logo_data

        lw = int(getattr(logo_airbuddy, "WIDTH", 0) or 0)
        lh = int(getattr(logo_airbuddy, "HEIGHT", 0) or 0)
        data = getattr(logo_airbuddy, "DATA", None)

        if (lw <= 0) or (lh <= 0) or (data is None):
            self._logo_lw, self._logo_lh, self._logo_data = 0, 0, None
            return 0, 0, None

        if not isinstance(data, (bytes, bytearray)):
            try:
                data = bytes(data)
            except Exception:
                self._logo_lw, self._logo_lh, self._logo_data = 0, 0, None
                return 0, 0, None

        self._logo_lw, self._logo_lh, self._logo_data = lw, lh, data
        return lw, lh, data

    def _logo_pixel(self, data, lw, x, y):
        idx = x + (y >> 3) * lw
        b = data[idx]
        return (b >> (y & 7)) & 1

    def _blit_logo_fixed(self, oled, x0, y0, lw, lh, data):
        sw = int(getattr(oled, "width", 128))
        sh = int(getattr(oled, "height", 64))
        fb = getattr(oled, "oled", None)
        if fb is None:
            return False

        for yy in range(lh):
            dy = (lh - 1 - yy) if self.flip_y else yy
            sy = y0 + yy
            if sy < 0 or sy >= sh:
                continue

            for xx in range(lw):
                dx = (lw - 1 - xx) if self.flip_x else xx
                sx = x0 + xx
                if sx < 0 or sx >= sw:
                    continue

                if self._logo_pixel(data, lw, dx, dy):
                    fb.pixel(sx, sy, 1)

        return True

    # ----------------------------
    # Time helpers (wrap-safe)
    # ----------------------------
    def _now_ms(self):
        try:
            return time.ticks_ms()
        except Exception:
            return int(time.time() * 1000)

    def _elapsed_ms(self, now_ms):
        if self._start_ms is None:
            self._start_ms = now_ms
            return 0
        try:
            return time.ticks_diff(now_ms, self._start_ms)
        except Exception:
            return now_ms - self._start_ms

    def _anim_step(self, period_ms=1000):
        now = self._now_ms()
        elapsed = self._elapsed_ms(now)
        p = int(period_ms) or 1000
        return int(elapsed // p) % 4

    def _animated_line(self, base, period_ms=1000):
        step = self._anim_step(period_ms)
        if step == 0:
            return base
        if step == 1:
            return base + "."
        if step == 2:
            return base + ".."
        return base + "..."

    # ----------------------------
    # Heartbeat mode selector
    #
    # We want:
    #   Offline: empty ring
    #   Online steady: SOLID ring
    #   Heartbeat: alternate empty <-> solid in a double-beat pattern
    #
    # Returns:
    #   api_mode = 0 => empty
    #   api_mode = 1 => solid
    # ----------------------------
    def _api_draw_mode(self, now_ms, api_ok=True):
        if not api_ok:
            return 0

        # position within cycle
        try:
            t = int(now_ms)
        except Exception:
            t = 0

        p = int(self._hb_cycle_ms) or 900
        m = int(t % p)

        b1 = int(self._hb_b1_ms)
        gap = int(self._hb_gap_ms)
        b2 = int(self._hb_b2_ms)

        # During beats: show EMPTY (pulse) alternating against steady SOLID background
        # So it "pops" (solid->empty->solid) without needing a third glyph.
        if m < b1:
            return 0  # beat1: empty
        if m < (b1 + gap):
            return 1  # between beats: solid
        if m < (b1 + gap + b2):
            return 0  # beat2: empty
        return 1      # rest: solid

    # ----------------------------
    # Safe sizing + centering
    # ----------------------------
    def _safe_text_size(self, writer, text):
        text = str(text or "")
        try:
            return writer.size(text)
        except MemoryError:
            return (len(text) * 6, 8)
        except Exception:
            return (len(text) * 6, 8)

    def _safe_center_write(self, oled, writer, text, y):
        text = str(text or "")
        w = int(getattr(oled, "width", 128))
        tw, _ = self._safe_text_size(writer, text)
        x = max(0, (w - int(tw)) // 2)
        try:
            writer.write(text, x, int(y))
        except MemoryError:
            try:
                writer.write(text, 0, int(y))
            except Exception:
                pass
        except Exception:
            pass

    # ----------------------------
    # Status icons (top-right) — ORDER: GPS  API  WIFI
    # api_mode:
    #   0 => empty ring (offline or heartbeat pulse)
    #   1 => solid ring (online steady)
    # ----------------------------
    def _draw_status_icons(self, oled, wifi_ok=False, gps_on=False, api_ok=False, api_mode=0):
        fb = getattr(oled, "oled", None)
        if fb is None:
            return

        w = int(getattr(oled, "width", 128))

        cluster_right_x = w - int(self.cluster_right_inset_px)
        y = int(self.icon_y)
        gap = int(self.icon_gap_px)

        WIFI_W = 9
        API_W = 7
        GPS_W = 14

        x = cluster_right_x

        # WIFI (rightmost)
        x -= WIFI_W
        try:
            draw_wifi(fb, x, y, on=bool(wifi_ok), color=1)
        except Exception:
            pass
        x -= gap

        # API (middle)
        x -= API_W
        try:
            # api_mode:
            #   0 => empty (offline or pulse)
            #   1 => solid (online steady)
            if int(api_mode) == 1:
                # solid version
                draw_api(fb, x, y, on=True, heartbeat=False, color=1)
            else:
                # empty version
                draw_api(fb, x, y, on=False, heartbeat=False, color=1)
        except Exception:
            pass
        x -= gap

        # GPS (leftmost)
        if gps_on:
            x -= GPS_W
            try:
                draw_gps(fb, x, y, color=1)
            except Exception:
                pass


    # ----------------------------
    # Core renderer (full screen)
    # ----------------------------
    def render(
            self,
            oled,
            line="Know your air...",
            animate=False,
            period_ms=1000,
            *,
            wifi_ok=False,
            gps_on=False,
            api_ok=False
    ):
        fb = getattr(oled, "oled", None)
        if fb is None:
            return

        ow = int(getattr(oled, "width", 128))
        oh = int(getattr(oled, "height", 64))

        fb.fill(0)

        writer = getattr(oled, "f_med", None) or getattr(oled, "f_small", None)
        if writer is None:
            return

        # Icons first
        # Offline => empty, Online => solid (baseline)
        api_mode = 1 if bool(api_ok) else 0
        self._draw_status_icons(oled, wifi_ok=wifi_ok, gps_on=gps_on, api_ok=api_ok, api_mode=api_mode)

        base = (line or "").rstrip().rstrip(". ")
        if not animate:
            line_to_draw = base + "..."
        else:
            line_to_draw = self._animated_line(base, period_ms)

        lw, lh, data = self._get_logo_cached()
        use_logo = (lw > 0 and lh > 0 and lw <= ow and lh <= oh and data is not None)

        _, line_h = self._safe_text_size(writer, line_to_draw)
        total_h = (lh + self.gap + line_h) if use_logo else line_h
        y_centered = max(0, (oh - total_h) // 2)

        logo_y = y_centered + self.logo_drop_px + int(self.logo_y_offset_px)

        if use_logo:
            logo_x = max(0, (ow - lw) // 2)
            ok = self._blit_logo_fixed(oled, logo_x, logo_y, lw, lh, data)
            line_y = (logo_y + lh + self.gap) if ok else logo_y
        else:
            line_y = logo_y

        line_y = int(line_y) + int(self.line_y_offset_px)

        self._safe_center_write(oled, writer, line_to_draw, line_y)

        fb.show()

        try:
            gc.collect()
        except Exception:
            pass
