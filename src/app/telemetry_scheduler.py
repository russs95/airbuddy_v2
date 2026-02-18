# src/app/telemetry_scheduler.py
# AirBuddy Telemetry Scheduler (Pico / MicroPython)
#
# Responsibilities:
# - Decide WHEN to attempt telemetry send (interval)
# - Build compact telemetry payload from latest reading
# - Persist "last sent" timestamp for Logging screen
# - Expose queue size + last sent helpers for UI
#
# FIX (Feb 2026):
# - AirSensor.read_quick() returns AirReading (object), NOT dict.
#   So build_values() must support attribute-style readings.
# - Re-enable real-data gate to stop DB spam.
# - Skip read_quick if sampling/warmup is in progress (avoid I2C collisions).
#
# RAM NOTES (Pico W):
# - Avoid heavy imports at top-level
# - Prefer ujson lazily
# - Avoid list(keys) allocations
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

        # Debug throttling
        self._dbg_every_n = 1
        self._dbg_count = 0

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
                j.dump({"ts": int(ts), "ok": bool(ok)}, f)
        except Exception:
            pass
        finally:
            _gc_collect()

    @staticmethod
    def queue_size():
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
    def _dbg_print(self, *parts):
        try:
            print(*parts)
        except Exception:
            pass

    def _ensure_client(self, cfg):
        if self._client is not None:
            return self._client

        # Lazy import (saves RAM during boot)
        from src.net.telemetry_client import TelemetryClient

        api_base = (cfg.get("api_base") or "").strip()
        device_id = (cfg.get("device_id") or "").strip()
        device_key = (cfg.get("device_key") or "").strip()

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

    def _sampling_in_progress(self):
        """
        Avoid telemetry reads while the button sampling warmup is active.
        This prevents I2C collisions + ENS retry loops overlapping.
        """
        a = self.air
        if a is None:
            return False

        # AirSensor sets _warmup_until during begin_sampling().
        try:
            wu = getattr(a, "_warmup_until", None)
            if wu is not None:
                # warmup is active until it expires (finish_sampling clears it)
                try:
                    if time.ticks_diff(time.ticks_ms(), wu) < 0:
                        return True
                except Exception:
                    return True
        except Exception:
            pass

        # If AirSensor provides is_ready(), treat "not ready" as "sampling in progress"
        try:
            if hasattr(a, "is_ready") and callable(a.is_ready):
                if not a.is_ready():
                    return True
        except Exception:
            pass

        return False

    def _build_values(self, reading, rtc_temp_c=None):
        """
        Convert reading into compact dict values.

        Supports:
        - dict readings (legacy/other sensors)
        - AirReading objects (your AirSensor.read_quick / finish_sampling)
        """
        values = {}

        # 1) AirReading/object path (preferred)
        if reading is not None and (not isinstance(reading, dict)):
            # Pull known fields with getattr (no allocations)
            try:
                eco2 = getattr(reading, "eco2_ppm", None)
                tvoc = getattr(reading, "tvoc_ppb", None)
                temp = getattr(reading, "temp_c", None)
                rh = getattr(reading, "humidity", None)
                aqi = getattr(reading, "aqi", None)
                ready = getattr(reading, "ready", None)
                conf = getattr(reading, "confidence", None)

                if eco2 is not None:
                    values["eco2_ppm"] = int(eco2)
                if tvoc is not None:
                    values["tvoc_ppb"] = int(tvoc)
                if temp is not None:
                    # keep as float but tiny
                    try:
                        values["temp_c"] = float(temp)
                    except Exception:
                        pass
                if rh is not None:
                    try:
                        values["rh"] = float(rh)
                    except Exception:
                        pass
                if aqi is not None:
                    try:
                        values["aqi"] = int(aqi)
                    except Exception:
                        pass
                if ready is not None:
                    values["ready"] = bool(ready)
                if conf is not None:
                    try:
                        values["confidence"] = int(conf)
                    except Exception:
                        pass
            except Exception:
                # fall through; may still try dict path below
                pass

        # 2) dict path
        if isinstance(reading, dict):
            def g(*keys):
                for k in keys:
                    try:
                        v = reading.get(k, None)
                    except Exception:
                        v = None
                    if v is not None:
                        return v
                return None

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

        # RTC temperature (optional)
        if rtc_temp_c is not None:
            try:
                values["rtc_temp_c"] = float(rtc_temp_c)
            except Exception:
                pass

        # If still empty, mark as placeholder (used by gate)
        if not values:
            values["note"] = "no_reading"

        return values

    def _values_has_real_data(self, values):
        """
        True if values contains at least one actual numeric sensor reading
        AND looks meaningful (prevents DB spam).
        """
        if not isinstance(values, dict) or not values:
            return False

        if values.get("note") == "no_reading":
            return False

        # If ready flag exists and is False => skip
        if ("ready" in values) and (not bool(values.get("ready"))):
            return False

        # Must have at least one meaningful numeric key
        eco2 = values.get("eco2_ppm", None)
        tvoc = values.get("tvoc_ppb", None)
        temp = values.get("temp_c", None)
        rh = values.get("rh", None)

        # eco2: must be > 0
        if isinstance(eco2, (int, float)) and eco2 > 0:
            return True

        # tvoc: allow >=0 (but require some other signal if 0)
        if isinstance(tvoc, (int, float)) and tvoc > 0:
            return True

        # temp/rh alone are allowed, but only if they look sane
        if isinstance(temp, (int, float)) and (-20.0 <= float(temp) <= 80.0):
            return True
        if isinstance(rh, (int, float)) and (0.0 <= float(rh) <= 100.0):
            return True

        return False

    def _dbg_values_sample(self, values, max_items=5):
        if not isinstance(values, dict):
            return
        n = 0
        try:
            for k in values:
                self._dbg_print("telemetry: val", k, "=", values.get(k))
                n += 1
                if n >= int(max_items):
                    break
        except Exception:
            pass

    # ----------------------------
    # Main tick
    # ----------------------------
    def tick(self, cfg, rtc_dict=None):
        """
        Call frequently from the main loop.
        """
        if not cfg or not cfg.get("telemetry_enabled", True):
            return

        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_send_ms) < 0:
            return

        # Schedule next send FIRST
        try:
            interval_s = int(cfg.get("telemetry_post_every_s", 120) or 120)
        except Exception:
            interval_s = 120
        if interval_s < 10:
            interval_s = 10

        self._next_send_ms = time.ticks_add(now, interval_s * 1000)

        # Debug: due
        self._dbg_count += 1
        do_print = (self._dbg_count % int(self._dbg_every_n)) == 0
        if do_print:
            self._dbg_print("telemetry: DUE interval_s=", interval_s)

        # Must have wifi
        if self.wifi:
            try:
                if not self.wifi.is_connected():
                    if do_print:
                        self._dbg_print("telemetry: skip (wifi not connected)")
                    return
            except Exception:
                if do_print:
                    self._dbg_print("telemetry: skip (wifi check error)")
                return

        # Skip if sampling warmup is active
        if self._sampling_in_progress():
            if do_print:
                self._dbg_print("telemetry: skip (sampling in progress)")
            return

        # Grab a quick reading (AirReading object)
        got_reading = False
        try:
            r = self.air.read_quick(source="telemetry")
            if r:
                self._last_reading = r
                got_reading = True
        except Exception as e:
            if do_print:
                self._dbg_print("telemetry: read_quick err", repr(e))

        # RTC temp (optional)
        rtc_temp_c = None
        if rtc_dict is None and self.get_rtc:
            try:
                rtc_dict = self.get_rtc()
            except Exception:
                rtc_dict = None
        if isinstance(rtc_dict, dict):
            rtc_temp_c = rtc_dict.get("temp_c")

        values = self._build_values(self._last_reading, rtc_temp_c=rtc_temp_c)

        recorded_at = self._now_unix_seconds()
        if recorded_at < 1000000000:
            if do_print:
                self._dbg_print("telemetry: skip (rtc not epoch) t=", recorded_at)
            return

        # ✅ REAL-DATA GATE (re-enabled)
        if not self._values_has_real_data(values):
            self.write_last_sent(recorded_at, ok=False)
            if do_print:
                self._dbg_print("telemetry: skip (no real data)", "reading=", "ok" if got_reading else "none")
                self._dbg_values_sample(values, max_items=6)
            return

        if do_print:
            self._dbg_print("telemetry: sending", "reading=", "ok" if got_reading else "none",
                            "values_len=", (len(values) if isinstance(values, dict) else 0))
            self._dbg_values_sample(values, max_items=6)

        payload = {
            "recorded_at": recorded_at,
            "values": values,
            "flags": {"auto_log": True},
        }

        client = self._ensure_client(cfg)

        ok = False
        msg = ""
        try:
            ok, msg = client.send(payload)
        except Exception as e:
            ok = False
            msg = "EXC " + repr(e)
        finally:
            _gc_collect()

        # Always update last_sent (lets UI show attempts)
        self.write_last_sent(recorded_at, ok=bool(ok))

        if do_print:
            self._dbg_print("telemetry:", ok, msg)
