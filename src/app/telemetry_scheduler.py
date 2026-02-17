# src/app/telemetry_scheduler.py
# AirBuddy Telemetry Scheduler (Pico / MicroPython)
#
# Responsibilities:
# - Decide WHEN to attempt telemetry send (interval)
# - Build compact telemetry payload from latest reading
# - Persist "last sent" timestamp for Logging screen
# - Expose queue size + last sent helpers for UI
#
# RAM NOTES (Pico W):
# - Avoid importing heavy modules at top-level
# - Avoid json.load/json.dump when possible (use ujson, lazy import)
# - Avoid list(reading.keys()) (allocates)
# - gc.collect() after file/network work

import time

LAST_SENT_FILE = "telemetry_last_sent.json"
QUEUE_FILE = "telemetry_queue.json"


def _json():
    """Lazy JSON import (prefer ujson)."""
    try:
        import ujson as _j
        return _j
    except Exception:
        import json as _j
        return _j


def _gc_collect():
    try:
        import gc
        gc.collect()
    except Exception:
        pass


class TelemetryScheduler:
    def __init__(self, air_sensor, rtc_info_getter=None, wifi_manager=None):
        """
        air_sensor: AirSensor instance (must support read_quick())
        rtc_info_getter: callable -> dict (e.g. lambda: rtc dict)
        wifi_manager: WiFiManager instance (must support is_connected())
        """
        self.air = air_sensor
        self.get_rtc = rtc_info_getter
        self.wifi = wifi_manager

        self._client = None
        self._next_send_ms = time.ticks_add(time.ticks_ms(), 3000)
        self._last_reading = None

    # ----------------------------
    # Public UI helpers
    # ----------------------------
    @staticmethod
    def read_last_sent():
        j = _json()
        try:
            with open(LAST_SENT_FILE, "r") as f:
                return j.load(f)
        except Exception:
            return None
        finally:
            _gc_collect()

    @staticmethod
    def write_last_sent(ts, ok=True):
        j = _json()
        try:
            with open(LAST_SENT_FILE, "w") as f:
                # keep it tiny
                j.dump({"ts": int(ts), "ok": bool(ok)}, f)
        except Exception:
            pass
        finally:
            _gc_collect()

    @staticmethod
    def queue_size():
        """
        Reads telemetry_queue.json as a list and returns its length.
        (If TelemetryClient uses a different format, returns 0 safely.)
        """
        j = _json()
        try:
            with open(QUEUE_FILE, "r") as f:
                q = j.load(f)
            return len(q) if isinstance(q, list) else 0
        except Exception:
            return 0
        finally:
            _gc_collect()

    # ----------------------------
    # Internal helpers
    # ----------------------------
    def _ensure_client(self, cfg):
        if self._client is not None:
            return self._client

        # Lazy import (saves RAM during boot)
        from src.net.telemetry_client import TelemetryClient

        api_base = (cfg.get("api_base") or "").strip()
        device_id = (cfg.get("device_id") or "").strip()
        device_key = (cfg.get("device_key") or "").strip()

        # Keep client minimal
        self._client = TelemetryClient(
            api_base=api_base,
            device_id=device_id,
            device_key=device_key
        )
        return self._client

    def _now_unix_seconds(self):
        try:
            return int(time.time())
        except Exception:
            return 0

    def _build_values(self, reading, rtc_temp_c=None):
        """
        Convert AirSensor reading dict into compact values.
        Keep tolerant to key name changes.
        """
        if not isinstance(reading, dict):
            return {"note": "no_reading"}

        def g(*keys):
            for k in keys:
                try:
                    v = reading.get(k, None)
                except Exception:
                    v = None
                if v is not None:
                    return v
            return None

        values = {}

        eco2 = g("eco2", "eCO2", "eco2_ppm", "co2_ppm", "co2")
        tvoc = g("tvoc", "tvoc_ppb")
        temp = g("temp_c", "temperature_c", "t_c")
        rh = g("rh", "humidity", "humidity_rh", "rh_pct")

        if eco2 is not None:
            values["eco2_ppm"] = eco2
        if tvoc is not None:
            values["tvoc_ppb"] = tvoc
        if temp is not None:
            values["temp_c"] = temp
        if rh is not None:
            values["rh"] = rh

        if rtc_temp_c is not None:
            try:
                values["rtc_temp_c"] = float(rtc_temp_c)
            except Exception:
                pass

        # If we still have nothing, do a bounded, no-list fallback.
        # (Avoids list(reading.keys()) allocations.)
        if not values:
            n = 0
            try:
                for k in reading:
                    v = reading.get(k)
                    if isinstance(v, (int, float, str, bool)) or v is None:
                        values[k] = v
                        n += 1
                    if n >= 12:
                        break
            except Exception:
                pass

        return values

    def _values_has_real_data(self, values):
        """
        True if values contains at least one actual numeric sensor reading.
        """
        if not isinstance(values, dict) or not values:
            return False

        if values.get("note") == "no_reading":
            return False

        real_keys = ("eco2_ppm", "tvoc_ppb", "temp_c", "rh", "pm25", "pm10", "aqi")
        for k in real_keys:
            v = values.get(k)
            if isinstance(v, (int, float)) and v is not None:
                return True

        return False

    # ----------------------------
    # Main tick
    # ----------------------------
    def tick(self, cfg, rtc_dict=None):
        """
        Call frequently from the main loop.

        cfg: dict from load_config()
        rtc_dict: rtc info dict (optional)
        """
        if not cfg or not cfg.get("telemetry_enabled", True):
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_send_ms) < 0:
            return

        # Schedule next send FIRST (prevents hammering on failures)
        try:
            interval_s = int(cfg.get("telemetry_post_every_s", 120) or 120)
        except Exception:
            interval_s = 120
        if interval_s < 10:
            interval_s = 10

        self._next_send_ms = time.ticks_add(now, interval_s * 1000)

        # Must have wifi
        if self.wifi:
            try:
                if not self.wifi.is_connected():
                    return
            except Exception:
                return

        # Grab a quick reading
        try:
            r = self.air.read_quick(source="telemetry")
            if r:
                self._last_reading = r
        except Exception:
            pass

        # RTC temp (optional)
        rtc_temp_c = None
        if rtc_dict is None and self.get_rtc:
            try:
                rtc_dict = self.get_rtc()
            except Exception:
                rtc_dict = None
        if isinstance(rtc_dict, dict):
            rtc_temp_c = rtc_dict.get("temp_c")

        values = self._build_values(self._last_reading or {}, rtc_temp_c=rtc_temp_c)

        recorded_at = self._now_unix_seconds()
        if recorded_at < 1000000000:
            return

        # Skip placeholder/no-reading payloads
        if not self._values_has_real_data(values):
            self.write_last_sent(recorded_at, ok=False)
            return

        payload = {
            "recorded_at": recorded_at,
            "values": values,
            "flags": {"auto_log": True},
        }

        # Ensure client lazily
        client = self._ensure_client(cfg)

        ok = False
        try:
            ok, _msg = client.send(payload)
        except Exception:
            ok = False
        finally:
            # Always collect after a send attempt; sockets/JSON can fragment RAM.
            _gc_collect()

        if ok:
            self.write_last_sent(recorded_at, ok=True)
