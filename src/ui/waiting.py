# src/ui/waiting.py  (MicroPython / Pico-safe)
#
# WAITING SCREEN
# - airBuddy logo + tagline
# - optional 3-dot animation
# - top-right status icons: GPS  API  WIFI
# - background idle hook (telemetry tick lives here)
#
# PATCH (Feb 2026 - stability + UI refresh):
# - FIX: OLED refresh must call oled.oled.show() (NOT fb.show()).
# - Reduce on_idle polling frequency to avoid RAM churn.
# - Stop REPL spam (log only on entry; optional debug toggle).
# - Always draw GPS icon (empty when not detected).
# - API heartbeat only when api_ok=True (and WiFi ok), sending forces filled.

import time
import gc
from src.ui import logo_airbuddy
from src.ui.glyphs import draw_wifi, draw_gps, draw_api


class WaitingScreen:
    def __init__(self, flip_x=False, flip_y=True, gap=6, logo_drop_px=10):
        self.flip_x = bool(flip_x)
        self.flip_y = bool(flip_y)

        self.gap = int(gap)
        self.logo_drop_px = int(logo_drop_px)

        self._start_ms = None

        self._logo_lw = None
        self._logo_lh = None
        self._logo_data = None

        self.logo_y_offset_px = -2
        self.line_y_offset_px = -6

        self.cluster_right_inset_px = 1
        self.icon_gap_px = 4
        self.icon_y = 1

        self.dots_period_ms = 1000
        self._last_dot_step = None

        # background idle scheduler
        self._idle_next_ms = 0

        # live status cache (updated by on_idle return)
        self._wifi_ok = False
        self._gps_on = False
        self._api_ok = False

        # optional "sending" pulse
        self._api_sending_until_ms = 0
        self.api_sending_hold_ms = 1200

        # last-render state
        self._last_wifi_ok = None
        self._last_gps_on = None
        self._last_api_ok = None
        self._last_api_sending = None

        # ---- DEBUG ----
        # Keep False in normal runs; turn on temporarily if diagnosing.
        self.log_status_checks = False

    # ============================================================
    # PUBLIC API (render once)
    # ============================================================
    def show(
            self,
            oled,
            line="Know your air...",
            animate=False,
            period_ms=1000,
            *,
            wifi_ok=False,
            gps_on=False,
            api_ok=False,
            api_sending=False,
    ):
        self._wifi_ok = bool(wifi_ok)
        self._gps_on = bool(gps_on)
        self._api_ok = bool(api_ok)

        if api_sending:
            now = self._now_ms()
            self._api_sending_until_ms = self._ticks_add(now, int(self.api_sending_hold_ms))

        self.render(
            oled,
            line=line,
            animate=animate,
            period_ms=period_ms,
            wifi_ok=self._wifi_ok,
            gps_on=self._gps_on,
            api_ok=self._api_ok,
            api_sending=self._is_api_sending(self._now_ms()),
        )

    # ============================================================
    # PUBLIC API (HOLD until click)
    # ============================================================
    def show_live(
            self,
            oled,
            btn,
            line="Know your air...",
            animate=True,
            period_ms=None,
            *,
            wifi_ok=False,
            gps_on=False,
            api_ok=False,
            poll_ms=25,
            flush_ms=220,
            on_idle=None,
            idle_every_ms=4000,   # <<<<< IMPORTANT: slow down background checks
    ):
        if period_ms is None:
            period_ms = int(self.dots_period_ms)

        # seed live status
        self._wifi_ok = bool(wifi_ok)
        self._gps_on = bool(gps_on)
        self._api_ok = bool(api_ok)

        # initial render
        self.render(
            oled,
            line=line,
            animate=bool(animate),
            period_ms=period_ms,
            wifi_ok=self._wifi_ok,
            gps_on=self._gps_on,
            api_ok=self._api_ok,
            api_sending=self._is_api_sending(self._now_ms()),
        )

        self._last_dot_step = self._anim_step(period_ms) if animate else None

        if btn is None:
            return None

        try:
            btn.reset()
        except Exception:
            pass

        # short flush of stale clicks
        try:
            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < int(flush_ms):
                try:
                    btn.poll_action()
                except Exception:
                    pass
                time.sleep_ms(int(poll_ms))
        except Exception:
            pass

        # schedule first background call
        now = self._now_ms()
        self._idle_next_ms = self._ticks_add(now, int(idle_every_ms))

        # --------------------------------------------------------
        # DO ONE STATUS CHECK ON ENTRY (and log once if enabled)
        # --------------------------------------------------------
        if on_idle is not None:
            try:
                ret = on_idle(now)
                if self.log_status_checks:
                    print("[WAITING] status check (entry) ->", ret)
                self._apply_idle_ret(ret, now)
            except Exception as e:
                if self.log_status_checks:
                    print("[WAITING] status check (entry) ERROR:", repr(e))

        # force redraw after entry check
        api_sending = self._is_api_sending(now)
        self.render(
            oled,
            line=line,
            animate=bool(animate),
            period_ms=period_ms,
            wifi_ok=self._wifi_ok,
            gps_on=self._gps_on,
            api_ok=self._api_ok,
            api_sending=api_sending,
        )
        self._remember_last(api_sending)

        # ========================================================
        # WAIT LOOP
        # ========================================================
        while True:
            now = self._now_ms()

            # ----------------------------------------------------
            # 1) Background idle hook (RARE)
            # ----------------------------------------------------
            if on_idle is not None:
                try:
                    if self._ticks_diff(now, self._idle_next_ms) >= 0:
                        ret = on_idle(now)
                        # no spam by default
                        if self.log_status_checks:
                            print("[WAITING] status check ->", ret)

                        self._apply_idle_ret(ret, now)
                        self._idle_next_ms = self._ticks_add(now, int(idle_every_ms))
                except Exception:
                    pass

            api_sending = self._is_api_sending(now)

            # ----------------------------------------------------
            # 2) Redraw only if needed
            # ----------------------------------------------------
            redraw = False

            if animate:
                try:
                    step = self._anim_step(period_ms)
                except Exception:
                    step = None
                if (step is not None) and (step != self._last_dot_step):
                    self._last_dot_step = step
                    redraw = True

            if (self._wifi_ok != self._last_wifi_ok or
                    self._gps_on != self._last_gps_on or
                    self._api_ok != self._last_api_ok or
                    api_sending != self._last_api_sending):
                redraw = True

            if redraw:
                self.render(
                    oled,
                    line=line,
                    animate=bool(animate),
                    period_ms=period_ms,
                    wifi_ok=self._wifi_ok,
                    gps_on=self._gps_on,
                    api_ok=self._api_ok,
                    api_sending=api_sending,
                )
                self._remember_last(api_sending)

            # ----------------------------------------------------
            # 3) Poll button
            # ----------------------------------------------------
            try:
                action = btn.poll_action()
            except Exception:
                action = None

            if action is not None:
                return action

            time.sleep_ms(int(poll_ms))

    # ============================================================
    # Helpers
    # ============================================================
    def _remember_last(self, api_sending):
        self._last_wifi_ok = self._wifi_ok
        self._last_gps_on = self._gps_on
        self._last_api_ok = self._api_ok
        self._last_api_sending = api_sending

    def _apply_idle_ret(self, ret, now_ms):
        if not isinstance(ret, dict):
            return
        if "wifi_ok" in ret:
            self._wifi_ok = bool(ret.get("wifi_ok"))
        if "gps_on" in ret:
            self._gps_on = bool(ret.get("gps_on"))
        if "api_ok" in ret:
            self._api_ok = bool(ret.get("api_ok"))

        # hold pulse
        if ret.get("api_sending", False):
            self._api_sending_until_ms = self._ticks_add(now_ms, int(self.api_sending_hold_ms))

    def _now_ms(self):
        try:
            return time.ticks_ms()
        except Exception:
            return int(time.time() * 1000)

    def _ticks_add(self, a, b):
        try:
            return time.ticks_add(a, b)
        except Exception:
            return a + b

    def _ticks_diff(self, a, b):
        try:
            return time.ticks_diff(a, b)
        except Exception:
            return a - b

    def _elapsed_ms(self, now_ms):
        if self._start_ms is None:
            self._start_ms = now_ms
            return 0
        return self._ticks_diff(now_ms, self._start_ms)

    def _anim_step(self, period_ms=1000):
        elapsed = self._elapsed_ms(self._now_ms())
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

    def _is_api_sending(self, now_ms):
        return self._ticks_diff(now_ms, self._api_sending_until_ms) < 0

    # ============================================================
    # LOGO
    # ============================================================
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

    # ============================================================
    # Status icons
    # ============================================================
    def _draw_status_icons(self, oled, wifi_ok=False, gps_on=False, api_ok=False, api_sending=False):
        fb = getattr(oled, "oled", None)
        if fb is None:
            return

        w = int(getattr(oled, "width", 128))

        cluster_right_x = w - int(self.cluster_right_inset_px)
        y = int(self.icon_y)
        gap = int(self.icon_gap_px)

        WIFI_W, WIFI_H = 9, 6
        API_W, API_H = 7, 6
        GPS_W, GPS_H = 14, 6

        x = cluster_right_x

        # WIFI
        x -= WIFI_W
        fb.fill_rect(x, y, WIFI_W, WIFI_H, 0)
        draw_wifi(fb, x, y, on=bool(wifi_ok), color=1)
        x -= gap

        # API
        # Heartbeat only if we *actually* consider API "healthy".
        api_connected = bool(wifi_ok) and bool(api_ok)

        x -= API_W
        fb.fill_rect(x, y, API_W, API_H, 0)
        draw_api(
            fb, x, y,
            on=api_connected,
            heartbeat=api_connected,     # breathe when connected
            sending=bool(api_sending),   # force filled during sends
            color=1
        )
        x -= gap

        # GPS (ALWAYS draw; empty when gps_on False)
        x -= GPS_W
        fb.fill_rect(x, y, GPS_W, GPS_H, 0)
        try:
            # preferred: new signature with on=
            draw_gps(fb, x, y, on=bool(gps_on), color=1)
        except TypeError:
            # fallback: legacy signature (will just draw one glyph)
            if gps_on:
                draw_gps(fb, x, y, color=1)
            else:
                # if legacy driver cannot draw "empty", we at least clear the box
                pass

    # ============================================================
    # Full render
    # ============================================================
    def render(
            self,
            oled,
            line="Know your air...",
            animate=False,
            period_ms=1000,
            *,
            wifi_ok=False,
            gps_on=False,
            api_ok=False,
            api_sending=False
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

        self._draw_status_icons(oled, wifi_ok, gps_on, api_ok, api_sending)

        base = (line or "").rstrip().rstrip(". ")
        p = int(period_ms) or 1000
        line_to_draw = base + "..." if not animate else self._animated_line(base, p)

        lw, lh, data = self._get_logo_cached()
        use_logo = (lw > 0 and lh > 0 and lw <= ow and lh <= oh and data is not None)

        try:
            _, line_h = writer.size(line_to_draw)
        except Exception:
            line_h = 8

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

        try:
            tw, _ = writer.size(line_to_draw)
            x = max(0, (ow - int(tw)) // 2)
        except Exception:
            x = 0

        try:
            writer.write(line_to_draw, x, int(line_y))
        except Exception:
            pass

        # CRITICAL FIX: show must be called on the OLED driver, not framebuffer
        try:
            oled.oled.show()
        except Exception:
            try:
                fb.show()
            except Exception:
                pass

        try:
            gc.collect()
        except Exception:
            pass