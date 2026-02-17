# src/ui/screens/logging.py
#
# Logging Screen:
# - Toggle logging on/off
# - Show interval (seconds)   (--- when OFF)
# - Show queue size           (--- when OFF; "empty" when ON and queue=0)
# - Show last sent timestamp  (always shown, even when OFF)
#
# Controls:
#   Single click: next screen  (with grace period so double-click can win)
#   Double click: toggle logging on/off

import time
from config import load_config, save_config
from src.ui.toggle import ToggleSwitch


class LoggingScreen:
    def __init__(self, oled):
        self.oled = oled
        self.toggle = ToggleSwitch(x=100, y=6, w=24, h=52)

        self._enabled = False
        self._interval = 120
        self._queue_size = None

        # already formatted by TelemetryState.get_last_sent()
        self._last_sent_text = "---"
        self._last_sent_ok = None

        self._next_refresh_ms = 0
        self._refresh_every_ms = 800

        # single-click grace to allow double-click detection
        self._single_grace_ms = 350

    # ----------------------------
    # Data refresh
    # ----------------------------
    def _reload_config(self):
        cfg = load_config()
        self._enabled = bool(cfg.get("telemetry_enabled", True))

        try:
            self._interval = int(cfg.get("telemetry_post_every_s", 120) or 120)
        except Exception:
            self._interval = 120

        if self._interval < 10:
            self._interval = 10

        return cfg

    def _apply_toggle(self):
        cfg = self._reload_config()
        self._enabled = not self._enabled
        cfg["telemetry_enabled"] = self._enabled
        save_config(cfg)

    def _refresh_runtime_stats(self, get_queue_size=None, get_last_sent=None):
        # Queue size
        if callable(get_queue_size):
            try:
                self._queue_size = int(get_queue_size())
            except Exception:
                self._queue_size = None
        else:
            self._queue_size = None

        # Last sent (already formatted by TelemetryState)
        self._last_sent_text = "---"
        self._last_sent_ok = None

        if callable(get_last_sent):
            try:
                last = get_last_sent()
                if isinstance(last, dict):
                    self._last_sent_text = str(last.get("text") or "---")
                    self._last_sent_ok = last.get("ok")
                elif last is None:
                    self._last_sent_text = "---"
                    self._last_sent_ok = None
                else:
                    self._last_sent_text = str(last)
                    self._last_sent_ok = None
            except Exception:
                self._last_sent_text = "---"
                self._last_sent_ok = None

    # ----------------------------
    # Drawing
    # ----------------------------
    def _draw(self):
        o = self.oled
        fb = o.oled
        fb.fill(0)

        # Title (moved UP by 2px)
        title_y = 2
        o.f_arvo20.write("Logging", 0, title_y)

        # "| ON/OFF" beside title in MED, caps
        try:
            title_w, _ = o._text_size(o.f_arvo20, "Logging")
        except Exception:
            title_w = 76

        state_text = "| ON" if self._enabled else "| OFF"
        o.f_med.write(state_text, title_w + 3, title_y + 4)

        # Toggle
        self.toggle.draw(fb, on=self._enabled)

        # Body block
        line_y = 24

        # Interval / Queue show --- when OFF
        if self._enabled:
            interval_str = "{}s".format(self._interval)

            if self._queue_size is None:
                q_str = "---"
            elif self._queue_size == 0:
                q_str = "empty"
            else:
                q_str = str(self._queue_size)
        else:
            interval_str = "---"
            q_str = "---"

        o.f_med.write(("Interval: " + interval_str)[:18], 0, line_y)
        o.f_med.write(("Queue: " + q_str)[:18], 0, line_y + 14)

        # Last always shown.
        # Label "Last:" in MED, timestamp in SMALL.
        last_str = self._last_sent_text or "---"
        if self._last_sent_ok is False and last_str != "---":
            last_str = last_str + "!"

        small = getattr(o, "f_small", None) or getattr(o, "f_arvo16", None) or o.f_med

        label = "Last: "
        o.f_med.write(label, 0, line_y + 28)

        # compute x offset for timestamp
        try:
            lw, _ = o._text_size(o.f_med, label)
        except Exception:
            lw = 6 * len(label)

        # write timestamp smaller
        small.write(str(last_str)[:14], lw, line_y + 30)  # +2px to visually align small font

        fb.show()

    # ----------------------------
    # Public
    # ----------------------------
    def show_live(self, btn, get_queue_size=None, get_last_sent=None):
        btn.reset()

        self._reload_config()
        self._refresh_runtime_stats(get_queue_size=get_queue_size, get_last_sent=get_last_sent)
        self._draw()

        self._next_refresh_ms = time.ticks_add(time.ticks_ms(), self._refresh_every_ms)

        pending_single_deadline = None

        while True:
            action = btn.poll_action()

            now = time.ticks_ms()

            # If we previously saw "single", wait briefly to see if it becomes "double"
            if pending_single_deadline is not None:
                if time.ticks_diff(now, pending_single_deadline) >= 0:
                    # no double arrived in time -> treat as next
                    return "next"

            if action == "single":
                # don't exit immediately; give double-click a chance
                pending_single_deadline = time.ticks_add(now, self._single_grace_ms)

            elif action == "double":
                # double-click wins: cancel pending single and toggle
                pending_single_deadline = None
                self._apply_toggle()
                self._reload_config()
                self._refresh_runtime_stats(get_queue_size=get_queue_size, get_last_sent=get_last_sent)
                self._draw()

                # IMPORTANT: clear any leftover click state so we don't immediately exit
                btn.reset()

            # periodic refresh
            if time.ticks_diff(now, self._next_refresh_ms) >= 0:
                self._reload_config()
                self._refresh_runtime_stats(get_queue_size=get_queue_size, get_last_sent=get_last_sent)
                self._draw()
                self._next_refresh_ms = time.ticks_add(now, self._refresh_every_ms)

            time.sleep_ms(25)
