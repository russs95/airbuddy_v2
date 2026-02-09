# src/ui/screens/time.py — Time + RTC info screen (Pico / MicroPython safe)

import time
from src.ui.glyphs import draw_circle, draw_degree


class TimeScreen:
    MONTHS = (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    )

    def __init__(self, oled):
        self.oled = oled

    # ----------------------------
    # Formatting
    # ----------------------------
    def _suffix(self, day):
        if 11 <= (day % 100) <= 13:
            return "th"
        last = day % 10
        return "st" if last == 1 else "nd" if last == 2 else "rd" if last == 3 else "th"

    def _pretty_date(self, date_str):
        try:
            if not date_str or date_str.startswith("--"):
                return "--"
            parts = date_str.split("/")
            if len(parts) != 3:
                return date_str
            d = int(parts[0]); m = int(parts[1]); y = int(parts[2])
            if not (1 <= m <= 12 and 1 <= d <= 31):
                return date_str
            return f"{self.MONTHS[m-1]} {d}{self._suffix(d)}, {y}"
        except Exception:
            return date_str

    def _blink_time(self, time_str, blink_on=True):
        # Turn ":" into " " when blink is off
        if not time_str or time_str.startswith("--"):
            return time_str
        if ":" in time_str:
            return time_str if blink_on else time_str.replace(":", " ", 1)
        return time_str

    # ----------------------------
    # Drawing blocks
    # ----------------------------
    def _draw_bottom_left_source(self, source, y):
        source = (source or "SYS").upper()
        filled = (source == "RTC")
        label = "RTC" if filled else "SYS"

        # Bigger circle to match MED font
        cx = 9
        cy = y + 8
        r = 4  # <- bigger than before
        draw_circle(self.oled.oled, cx, cy, r=r, filled=filled, color=1)

        # Label in MED
        self.oled.f_med.write(label, 18, y)

    def _draw_bottom_right_temp(self, temp_c, y):
        if temp_c is None:
            return
        try:
            t = int(round(float(temp_c)))
        except Exception:
            return

        # Draw: <t> + degree ring + C  (all MED, degree drawn in pixels)
        t_text = str(t)
        w_t, _ = self.oled._text_size(self.oled.f_med, t_text)
        w_c, _ = self.oled._text_size(self.oled.f_med, "C")

        deg_r = 2
        deg_w = deg_r * 2 + 1  # ~5px
        total_w = w_t + 1 + deg_w + 1 + w_c

        x0 = max(0, self.oled.width - total_w - 2)

        self.oled.f_med.write(t_text, x0, y)

        x_deg = x0 + w_t + 1
        y_deg = y + 2
        draw_degree(self.oled.oled, x_deg, y_deg, r=deg_r, color=1)

        x_c = x_deg + deg_w + 1
        self.oled.f_med.write("C", x_c, y)

    def _render(self, date_str, time_str, source="SYS", temp_c=None, blink_on=True):
        self.oled.oled.fill(0)

        # --- Top: pretty date (MED) ---
        pretty = self._pretty_date(date_str)
        _, h_med = self.oled._text_size(self.oled.f_med, pretty)
        self.oled.draw_centered(self.oled.f_med, pretty, 0)

        # --- Bottom row layout (MED height) ---
        _, h_bottom = self.oled._text_size(self.oled.f_med, "Ag")
        y_bottom = max(0, self.oled.height - h_bottom - 1)

        # --- Center: time (LARGE, with blinking colon) ---
        t_disp = self._blink_time(time_str, blink_on=blink_on)
        _, h_large = self.oled._text_size(self.oled.f_large, t_disp)

        top_block = h_med + 2
        bottom_block = y_bottom - 1
        available = max(0, bottom_block - top_block)
        y_time = top_block + max(0, (available - h_large) // 2)

        self.oled.draw_centered(self.oled.f_large, t_disp, y_time)

        # --- Bottom-left/source + bottom-right/temp ---
        self._draw_bottom_left_source(source, y_bottom)
        self._draw_bottom_right_temp(temp_c, y_bottom)

        self.oled.oled.show()

    # ----------------------------
    # Public: static show
    # ----------------------------
    def show(self, date_str, time_str, source="SYS", temp_c=None):
        self._render(date_str, time_str, source=source, temp_c=temp_c, blink_on=True)

    # ----------------------------
    # Public: live show with blink + optional "hold until click"
    # ----------------------------
    def show_live(
            self,
            get_date_str,
            get_time_str,
            get_source,
            get_temp_c,
            btn=None,
            max_seconds=8,
            blink_ms=500,
            refresh_every_blinks=2
    ):
        """
        Live time screen with blinking ":".
        - Updates display every blink_ms (default 500ms).
        - Refreshes date/time/temp every N blinks (default 2 => 1s refresh).

        Holding indefinitely:
        - Only if we can poll button non-blocking.
        - If we can't, we fall back to max_seconds and return.

        btn: your AirBuddyButton instance (optional)
        """
        start = time.ticks_ms()
        blink_on = True
        blink_count = 0

        # Determine if we can non-blocking check for a click.
        # We will NOT call a blocking wait_for_action() here.
        can_poll = False
        poll_fn = None

        if btn is not None:
            # If your button class exposes a non-blocking method, use it.
            # Common patterns:
            #   - btn.poll()
            #   - btn.check()
            #   - btn.read()
            for name in ("poll", "check", "read", "get_action_nonblocking"):
                if hasattr(btn, name):
                    poll_fn = getattr(btn, name)
                    can_poll = True
                    break

        # If we can't poll, do NOT hold indefinitely
        if not can_poll:
            hold_forever = False
        else:
            hold_forever = (max_seconds is None) or (max_seconds <= 0)

        # Prime values
        date_str = get_date_str()
        time_str = get_time_str()
        source = get_source()
        temp_c = get_temp_c()

        while True:
            # Toggle blink
            blink_on = not blink_on
            blink_count += 1

            # Refresh values every N blinks (e.g. every 1s if blink=500ms, N=2)
            if blink_count % max(1, int(refresh_every_blinks)) == 0:
                date_str = get_date_str()
                time_str = get_time_str()
                source = get_source()
                temp_c = get_temp_c()

            self._render(date_str, time_str, source=source, temp_c=temp_c, blink_on=blink_on)

            # Exit conditions
            if can_poll and poll_fn:
                try:
                    action = poll_fn()
                    # Any recognized action exits (single/double/debug)
                    if action:
                        return action
                except Exception:
                    # If polling fails, stop trying and revert to timed exit
                    can_poll = False

            if not hold_forever:
                if time.ticks_diff(time.ticks_ms(), start) >= int(max_seconds * 1000):
                    return None

            time.sleep_ms(int(blink_ms))
