# src/ui/screens/time.py

import time
import json
import gc
import machine

from src.ui.glyphs import draw_circle, draw_degree

try:
    import urequests
except Exception:
    urequests = None

CONFIG_FILE = "config.json"

MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]


class TimeScreen:
    def __init__(self, oled, cfg, wifi_manager=None, rtc_info=None, ds3231=None):
        self.oled = oled
        self.cfg = cfg

        # Optional helpers
        self.wifi = wifi_manager
        self.rtc_info = rtc_info if isinstance(rtc_info, dict) else {}
        self.ds3231 = ds3231

        # API refresh happens once per screen open
        self._tz_checked = False

    # -------------------------------------------------
    # RTC / tuples
    # -------------------------------------------------
    def _get_utc_tuple(self):
        # System RTC is expected to be UTC
        return time.localtime()

    def _get_user_time_tuple(self):
        offset_min = self.cfg.get("timezone_offset_min", None)
        if offset_min is None:
            return None

        try:
            offset_min = int(offset_min)
        except Exception:
            return None

        utc_ts = time.time()
        local_ts = utc_ts + (offset_min * 60)
        return time.localtime(local_ts)

    def _sync_rtc_from_server_ts(self, ts_ms):
        """
        Set system RTC to UTC using server epoch milliseconds.
        Safe no-op on any error.
        """
        try:
            epoch_s = int(ts_ms) // 1000
            y, mo, d, hh, mm, ss, wday, _ = time.gmtime(epoch_s)
            machine.RTC().datetime((y, mo, d, wday, hh, mm, ss, 0))
        except Exception:
            pass

    # -------------------------------------------------
    # API refresh (once) + offline-safe gating
    # -------------------------------------------------
    def _refresh_from_api_once(self):
        if self._tz_checked:
            return
        self._tz_checked = True

        if not urequests:
            return

        if not self.cfg.get("wifi_enabled", False):
            return

        # Require actual WiFi connection (prevents blocking offline)
        if self.wifi:
            try:
                if not self.wifi.is_connected():
                    return
            except Exception:
                return

        api_base = self.cfg.get("api_base")
        device_id = self.cfg.get("device_id")
        device_key = self.cfg.get("device_key")

        if not (api_base and device_id and device_key):
            return

        url = api_base.rstrip("/") + "/v1/device?compact=1"
        headers = {
            "X-Device-Id": str(device_id),
            "X-Device-Key": str(device_key),
        }

        resp = None
        try:
            gc.collect()
            resp = urequests.get(url, headers=headers, timeout=4)

            if resp.status_code != 200:
                return

            data = resp.json()
            if not isinstance(data, dict) or not data.get("ok"):
                return

            # timezone offset update (cache in config.json)
            tz_off = data.get("timezone_offset_min", None)
            if tz_off is None:
                tz_off = data.get("tz_offset_min", None)

            if tz_off is not None:
                try:
                    tz_off = int(tz_off)

                    old = self.cfg.get("timezone_offset_min", None)
                    try:
                        old = int(old) if old is not None else None
                    except Exception:
                        old = None

                    if old != tz_off:
                        self.cfg["timezone_offset_min"] = tz_off
                        with open(CONFIG_FILE, "w") as f:
                            json.dump(self.cfg, f)
                except Exception:
                    pass

            # RTC sync from server epoch
            ts_ms = data.get("ts", None)
            if ts_ms is not None:
                self._sync_rtc_from_server_ts(ts_ms)

        except Exception:
            pass
        finally:
            try:
                if resp:
                    resp.close()
            except Exception:
                pass
            gc.collect()

    # -------------------------------------------------
    # Formatting helpers
    # -------------------------------------------------
    def _ordinal(self, n):
        if 10 <= n % 100 <= 20:
            suf = "th"
        else:
            suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return str(n) + suf

    def _fmt_date_long(self, t):
        day = self._ordinal(int(t[2]))
        month = MONTHS[int(t[1]) - 1]
        year = int(t[0])
        return "{} {}, {}".format(month, day, year)

    def _fmt_time_blink(self, t):
        # clean 1Hz blink: colon visible on even seconds
        s = int(t[5])
        colon = ":" if (s % 2 == 0) else " "
        return "{:02d}{}{:02d}".format(int(t[3]), colon, int(t[4]))

    # -------------------------------------------------
    # UI helpers
    # -------------------------------------------------
    def _is_rtc_detected(self):
        try:
            return bool(self.rtc_info.get("detected"))
        except Exception:
            return False

    def _draw_top_right_rtc_glyph(self, y=2):
        """
        Small circle glyph next to the date (top-right).
        Filled when RTC is detected (or you can invert if you prefer).
        """
        fb = getattr(self.oled, "oled", None)
        if fb is None:
            return

        r = 4
        filled = self._is_rtc_detected()

        # Position: right edge, with a tiny margin
        cx = int(self.oled.width) - (r + 2)
        cy = int(y) + (r + 1)

        draw_circle(fb, cx, cy, r=r, filled=filled, color=1)

    # -------------------------------------------------
    # Bottom row
    # -------------------------------------------------
    def _draw_bottom_left_temp(self, y):
        fb = getattr(self.oled, "oled", None)

        # Build temperature string (number only here; we draw degree glyph manually)
        temp_val = None

        if self.ds3231:
            try:
                temp_val = float(self.ds3231.temperature())
            except Exception:
                temp_val = None

        if temp_val is None:
            try:
                tv = self.rtc_info.get("temp_c", None)
                if tv is not None:
                    temp_val = float(tv)
            except Exception:
                temp_val = None

        if temp_val is None:
            # fallback plain
            self.oled.f_med.write("--.- C", 2, y)
            return

        # Write number
        num_str = "{:.1f}".format(temp_val)
        x = 2
        self.oled.f_med.write(num_str, x, y)

        # Compute where to draw the degree ring + "C"
        try:
            w_num, _ = self.oled._text_size(self.oled.f_med, num_str)
        except Exception:
            w_num = len(num_str) * 8  # rough fallback

        # Degree glyph
        if fb is not None:
            # Place degree ring just after number, slightly above baseline
            deg_x = x + int(w_num) + 1
            deg_y = y + 2
            draw_degree(fb, deg_x, deg_y, r=2, color=1)

            # Now write "C" after degree ring with a small gap
            self.oled.f_med.write("C", deg_x + 7, y)

    def _draw_bottom_right_utc(self, y):
        utc = self._get_utc_tuple()
        utc_str = "{:02d}:{:02d} UTC".format(int(utc[3]), int(utc[4]))

        w, _ = self.oled._text_size(self.oled.f_med, utc_str)
        x = max(0, self.oled.width - w - 2)
        self.oled.f_med.write(utc_str, x, y)

    # -------------------------------------------------
    # Render
    # -------------------------------------------------
    def _render(self):
        self.oled.oled.fill(0)

        user_t = self._get_user_time_tuple()

        if user_t is None:
            date_str = "NO:TZ"
            time_str = "NO:TZ"
        else:
            date_str = self._fmt_date_long(user_t)
            time_str = self._fmt_time_blink(user_t)

        # Top date (centered)
        self.oled.draw_centered(self.oled.f_med, date_str, 0)

        # RTC circle glyph at top-right, adjacent to date row
        self._draw_top_right_rtc_glyph(y=1)

        # Main time: TRUE centered (no width-jitter when colon blinks)
        # Use a fixed-width reference "88:88" for centering math.
        w_ref, h_ref = self.oled._text_size(self.oled.f_large, "88:88")
        x_time = max(0, (self.oled.width - w_ref) // 2)
        y_time = max(0, (self.oled.height - h_ref) // 2)

        try:
            self.oled.f_large.write(time_str, x_time, y_time)
        except Exception:
            # fallback to draw_centered if writer write fails
            self.oled.draw_centered(self.oled.f_large, time_str, y_time)

        # Bottom row
        _, h_bottom = self.oled._text_size(self.oled.f_med, "Ag")
        y_bottom = self.oled.height - h_bottom - 1

        self._draw_bottom_left_temp(y_bottom)
        self._draw_bottom_right_utc(y_bottom)

        self.oled.oled.show()

    # -------------------------------------------------
    # Public
    # -------------------------------------------------
    def show_live(self, btn=None, max_seconds=8):
        # Try API once on entry; safe no-op offline
        self._refresh_from_api_once()

        start_ms = time.ticks_ms()

        # Entry settle: drain any tail click so user can exit immediately
        if btn:
            try:
                t0 = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), t0) < 120:
                    try:
                        btn.poll_action()
                    except Exception:
                        pass
                    time.sleep_ms(15)
            except Exception:
                pass

        # Redraw throttling: update when the second changes (or at least every 350ms)
        last_sec = None
        last_draw_ms = 0

        # Poll fast so short taps register
        poll_ms = 25
        min_redraw_ms = 350

        while True:
            now_ms = time.ticks_ms()

            # --- Fast button polling ---
            if btn:
                try:
                    action = btn.poll_action()
                except Exception:
                    action = None
                if action:
                    return action

            # --- Decide whether to redraw ---
            try:
                utc = time.localtime()
                sec = int(utc[5])
            except Exception:
                sec = None

            redraw = False
            if sec is not None and sec != last_sec:
                redraw = True
                last_sec = sec
            elif time.ticks_diff(now_ms, last_draw_ms) >= min_redraw_ms:
                redraw = True

            if redraw:
                self._render()
                last_draw_ms = now_ms

            # --- Exit timer ---
            if max_seconds:
                if time.ticks_diff(now_ms, start_ms) >= int(max_seconds) * 1000:
                    return None

            time.sleep_ms(poll_ms)