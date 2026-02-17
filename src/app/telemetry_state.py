# src/app/telemetry_state.py — Telemetry state wrapper for AirBuddy (Pico / MicroPython safe)
#
# last_sent formatting responsibility lives HERE.

import time
from src.app.telemetry_scheduler import TelemetryScheduler


class TelemetryState:
    """
    Owns the TelemetryScheduler instance and exposes a small, stable interface
    for the runtime/UI layers.
    """

    def __init__(self, air_sensor, rtc_info_getter, wifi_manager):
        self.scheduler = TelemetryScheduler(
            air_sensor=air_sensor,
            rtc_info_getter=rtc_info_getter,
            wifi_manager=wifi_manager,
        )

    # ------------------------------------------------------------
    # Main loop integration
    # ------------------------------------------------------------
    def tick(self, cfg, rtc_dict=None):
        """
        Background telemetry attempt (only when due + enabled).
        """
        self.scheduler.tick(cfg, rtc_dict=rtc_dict)

    # ------------------------------------------------------------
    # Helpers for UI
    # ------------------------------------------------------------
    @staticmethod
    def get_queue_size():
        """
        Returns current queue size (int).
        Delegates to TelemetryScheduler's queue helper.
        """
        return TelemetryScheduler.queue_size()

    @staticmethod
    def _fmt_ts(ts):
        """
        Convert unix seconds -> "MM/DD-HH:MM"
        Example: 02/17-12:01

        If missing, return "---"
        """
        if ts is None:
            return "---"

        try:
            t = time.localtime(int(ts))
            mo = t[1]
            dd = t[2]
            hh = t[3]
            mm = t[4]
            return "{:02d}/{:02d}-{:02d}:{:02d}".format(mo, dd, hh, mm)
        except Exception:
            try:
                return str(int(ts))
            except Exception:
                return "---"

    @staticmethod
    def get_last_sent():
        """
        Returns a dict suitable for UI:
          {
            "ts": <int|None>,
            "ok": <bool|None>,
            "text": "MM/DD-HH:MM" | "---"
          }

        Supports older TelemetryScheduler.read_last_sent() returns:
        - dict: {"ts": int, "ok": bool}
        - int/str (timestamp)
        - None
        """
        last = None
        try:
            last = TelemetryScheduler.read_last_sent()
        except Exception:
            last = None

        ts = None
        ok = None

        if isinstance(last, dict):
            ts = last.get("ts")
            ok = last.get("ok")
        elif last is None:
            ts = None
            ok = None
        else:
            try:
                ts = int(last)
            except Exception:
                ts = None
            ok = None

        return {
            "ts": ts,
            "ok": ok,
            "text": TelemetryState._fmt_ts(ts),
        }
