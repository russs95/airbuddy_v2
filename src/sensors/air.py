# src/sensors/air.py  (MicroPython / Pico W) — Pico-safe
#
# Patch (AHT10 + AHT21 support):
# - Adds OPTIONAL AHT10 support (uses src.drivers.aht10.AHT10 if present)
# - Keeps AHT21 + ENS160 path as before
# - Stores BOTH sensor readings side-by-side on AirReading:
#     r.aht10_temp_c, r.aht10_humidity
#     r.aht21_temp_c, r.aht21_humidity
# - Chooses a "primary" temp/rh for ENS160 compensation + UI:
#     Prefer AHT21 (on the ENS stack), else AHT10, else 0/0 fallback
#
# IMPORTANT NOTE ABOUT ADDRESS CONFLICTS:
# - AHT10 and AHT21 usually both use I2C address 0x38.
# - If you physically connect *two* 0x38 devices to the SAME I2C bus,
#   they WILL conflict (both answer at once) and reads may be garbage.
# - To truly compare two separate 0x38 sensors, you need:
#     * TCA9548A mux, OR
#     * put one sensor on a second I2C bus (different pins), OR
#     * a sensor with a different address.
#
# This code supports a SECOND I2C bus for AHT10 (optional),
# so you can compare safely once you wire it that way.

import time
from machine import Pin, I2C

# ---- CO2 confidence helper (your implemented file) ----
try:
    from src.sensors.co2_confidence import calculate_co2_confidence
except Exception:
    calculate_co2_confidence = None


class AirReading:
    """
    Lightweight reading container (Pico-safe).

    ready:
      - True means ENS160 data passed basic validity checks.
      - False means sensor wasn't ready / values unreliable.
    confidence:
      - 1..100 confidence percentage if available
      - None if not calculated / unavailable (UI should show XX%)

    Side-by-side comparison (optional):
      - aht10_temp_c / aht10_humidity
      - aht21_temp_c / aht21_humidity
    """

    def __init__(
            self,
            timestamp,
            temp_c,
            humidity,
            eco2_ppm,
            tvoc_ppb,
            aqi,
            rating,
            source,
            ready=True,
            confidence=None,
            reason="",
            aht10_temp_c=None,
            aht10_humidity=None,
            aht21_temp_c=None,
            aht21_humidity=None,
    ):
        self.timestamp = int(timestamp)

        # Primary values used by UI + telemetry
        self.temp_c = float(temp_c)
        self.humidity = float(humidity)

        self.eco2_ppm = int(eco2_ppm)
        self.tvoc_ppb = int(tvoc_ppb)
        self.aqi = int(aqi)
        self.rating = str(rating)
        self.source = str(source)
        self.ready = bool(ready)
        self.confidence = None if confidence is None else int(confidence)
        self.reason = str(reason)

        # Optional comparison fields
        self.aht10_temp_c = aht10_temp_c
        self.aht10_humidity = aht10_humidity
        self.aht21_temp_c = aht21_temp_c
        self.aht21_humidity = aht21_humidity


# ----------------------------
# Minimal AHT21 driver
# ----------------------------
class AHT21:
    def __init__(self, i2c, addr=0x38):
        self.i2c = i2c
        self.addr = addr

    def read(self):
        # Trigger
        self.i2c.writeto(self.addr, b"\xAC\x33\x00")
        time.sleep_ms(85)

        data = self.i2c.readfrom(self.addr, 6)
        raw_h = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4)) & 0xFFFFF
        raw_t = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5]) & 0xFFFFF

        humidity = raw_h * 100.0 / 1048576.0
        temp_c = raw_t * 200.0 / 1048576.0 - 50.0
        return temp_c, humidity


# ----------------------------
# Minimal ENS160 driver
# ----------------------------
class ENS160:
    _REG_PART_ID = 0x00
    _REG_OPMODE = 0x10
    _REG_TEMP_IN = 0x13
    _REG_RH_IN = 0x15
    _REG_DATA_AQI = 0x21
    _REG_DATA_TVOC = 0x22
    _REG_DATA_ECO2 = 0x24

    _OPMODE_STD = 0x02

    def __init__(self, i2c, addr=0x53):
        self.i2c = i2c
        self.addr = addr
        self._init()

    def _read(self, reg, n):
        self.i2c.writeto(self.addr, bytes([reg]))
        return self.i2c.readfrom(self.addr, n)

    def _write8(self, reg, val):
        self.i2c.writeto(self.addr, bytes([reg, val & 0xFF]))

    def _write16(self, reg, val):
        self.i2c.writeto(self.addr, bytes([reg, val & 0xFF, (val >> 8) & 0xFF]))

    def _init(self):
        _ = self._read(self._REG_PART_ID, 2)
        self._write8(self._REG_OPMODE, self._OPMODE_STD)
        time.sleep_ms(50)

    def set_environment(self, temp_c, rh):
        temp_k = float(temp_c) + 273.15
        tval = int(temp_k * 64)
        hval = int(float(rh) * 512)
        self._write16(self._REG_TEMP_IN, tval)
        self._write16(self._REG_RH_IN, hval)

    def read_air_raw(self):
        aqi = self._read(self._REG_DATA_AQI, 1)[0]
        tvoc = self._read(self._REG_DATA_TVOC, 2)
        eco2 = self._read(self._REG_DATA_ECO2, 2)

        tvoc_ppb = tvoc[0] | (tvoc[1] << 8)
        eco2_ppm = eco2[0] | (eco2[1] << 8)
        return aqi, tvoc_ppb, eco2_ppm


class AirSensor:
    """
    AirSensor:
      - ENS160 + AHT21 (usual ENS stack)
      - OPTIONAL AHT10 (external module)
      - begin_sampling()/finish_sampling() warmup timer
      - ENS160 retry loop
      - confidence score attached to AirReading.confidence

    ESP32/Pico portability:
      - If i2c is not provided, pins are taken from src.hal.board.i2c_pins()
      - Hardware init is lazy (done on first actual read)

    Optional second bus for AHT10:
      - If you want to compare AHT10 vs AHT21 safely (no 0x38 conflict),
        wire AHT10 to a different I2C bus and pass aht10_i2c_* params.
    """

    def __init__(
            self,
            i2c=None,
            i2c_id=None,
            pin_sda=None,
            pin_scl=None,
            freq=None,
            aht21_addr=0x38,
            ens160_addr=0x53,
            # Optional: second I2C bus for AHT10 (recommended if also using AHT21 on 0x38)
            aht10_i2c=None,
            aht10_i2c_id=None,
            aht10_pin_sda=None,
            aht10_pin_scl=None,
            aht10_freq=None,
            log_path="air_records.csv",
            auto_init=False,
    ):
        self.log_path = log_path

        # Primary bus config (ENS160 + AHT21 typically)
        self._i2c = i2c
        self._i2c_id = i2c_id
        self._pin_sda = pin_sda
        self._pin_scl = pin_scl
        self._freq = freq

        # Optional AHT10 bus config
        self._aht10_i2c = aht10_i2c
        self._aht10_i2c_id = aht10_i2c_id
        self._aht10_pin_sda = aht10_pin_sda
        self._aht10_pin_scl = aht10_pin_scl
        self._aht10_freq = aht10_freq

        self._aht_addr = aht21_addr
        self._ens_addr = ens160_addr

        self._aht = None        # AHT21
        self._ens = None        # ENS160
        self._aht10 = None      # AHT10 (optional)

        self._warmup_until = None
        self._warmup_source = None

        self._last = None
        self._last_eco2_ppm = None
        self._last_aqi = None

        self._log_inited = False

        if auto_init:
            self._ensure_hw()

    # ----------------------------
    # Hardware init (lazy + HAL)
    # ----------------------------
    def _ensure_hw(self):
        # Primary I2C bus
        if self._i2c is None:
            # Prefer HAL-provided pins unless explicitly provided
            if self._pin_sda is None or self._pin_scl is None or self._i2c_id is None or self._freq is None:
                try:
                    from src.hal.board import i2c_pins
                    sda, scl, bus_id, hz = i2c_pins()
                    if self._pin_sda is None:
                        self._pin_sda = sda
                    if self._pin_scl is None:
                        self._pin_scl = scl
                    if self._i2c_id is None:
                        self._i2c_id = bus_id
                    if self._freq is None:
                        self._freq = hz
                except Exception:
                    if self._i2c_id is None:
                        self._i2c_id = 0
                    if self._pin_sda is None:
                        self._pin_sda = 0
                    if self._pin_scl is None:
                        self._pin_scl = 1
                    if self._freq is None:
                        self._freq = 100_000

            self._i2c = I2C(
                int(self._i2c_id),
                sda=Pin(int(self._pin_sda)),
                scl=Pin(int(self._pin_scl)),
                freq=int(self._freq),
            )

        # Instantiate primary drivers
        if self._aht is None:
            self._aht = AHT21(self._i2c, addr=self._aht_addr)
        if self._ens is None:
            self._ens = ENS160(self._i2c, addr=self._ens_addr)

        # AHT10 optional bus: if not provided, we will try to use the primary bus
        if self._aht10_i2c is None and (self._aht10_i2c_id is not None or self._aht10_pin_sda is not None or self._aht10_pin_scl is not None):
            # Build explicit AHT10 bus
            try:
                bus_id = 1 if self._aht10_i2c_id is None else int(self._aht10_i2c_id)
                sda = 2 if self._aht10_pin_sda is None else int(self._aht10_pin_sda)
                scl = 3 if self._aht10_pin_scl is None else int(self._aht10_pin_scl)
                hz = 100_000 if self._aht10_freq is None else int(self._aht10_freq)
                self._aht10_i2c = I2C(bus_id, sda=Pin(sda), scl=Pin(scl), freq=hz)
            except Exception:
                self._aht10_i2c = None

        # Instantiate AHT10 (best effort)
        if self._aht10 is None:
            try:
                from src.drivers.aht10 import AHT10
                bus = self._aht10_i2c if self._aht10_i2c is not None else self._i2c
                self._aht10 = AHT10(bus)
            except Exception:
                self._aht10 = None

        # Lazy init log header
        if not self._log_inited:
            self._ensure_log_header()
            self._log_inited = True

    # ----------------------------
    # Rating
    # ----------------------------
    @staticmethod
    def _rating_from_aqi(aqi):
        if aqi <= 1:
            return "Very good"
        if aqi == 2:
            return "Good"
        if aqi == 3:
            return "Ok"
        return "Poor"

    # ----------------------------
    # Timestamp
    # ----------------------------
    @staticmethod
    def _now_timestamp():
        try:
            return int(time.time())
        except Exception:
            return 0

    # ----------------------------
    # Validity heuristic
    # ----------------------------
    @staticmethod
    def _ens_values_look_ready(aqi, tvoc_ppb, eco2_ppm):
        if aqi < 1 or aqi > 5:
            return False
        if eco2_ppm <= 0:
            return False
        if eco2_ppm > 60000:
            return False
        if tvoc_ppb > 65000:
            return False
        return True

    def _read_ens160_with_retry(self, temp_c, rh, timeout_ms=4000, step_ms=250):
        start = time.ticks_ms()
        last = None

        while time.ticks_diff(time.ticks_ms(), start) < int(timeout_ms):
            try:
                self._ens.set_environment(temp_c, rh)
            except Exception:
                pass

            try:
                aqi, tvoc_ppb, eco2_ppm = self._ens.read_air_raw()
                last = (aqi, tvoc_ppb, eco2_ppm)
                if self._ens_values_look_ready(aqi, tvoc_ppb, eco2_ppm):
                    return aqi, tvoc_ppb, eco2_ppm, True, ""
            except Exception:
                last = None

            time.sleep_ms(int(step_ms))

        if last is None:
            return 0, 0, 0, False, "ens160 read failed"
        return last[0], last[1], last[2], False, "ens160 not ready"

    # ----------------------------
    # Confidence inputs
    # ----------------------------
    @staticmethod
    def _temp_ok(temp_c):
        return (-10.0 <= float(temp_c) <= 60.0)

    @staticmethod
    def _rh_ok(rh):
        return (0.0 <= float(rh) <= 100.0)

    # ----------------------------
    # Core read
    # ----------------------------
    def _read_once(self, source, warmup_done):
        self._ensure_hw()

        # Read AHT21 (best effort)
        aht21_temp, aht21_rh = None, None
        try:
            aht21_temp, aht21_rh = self._aht.read()
        except Exception:
            pass

        # Read AHT10 (best effort)
        aht10_temp, aht10_rh = None, None
        if self._aht10 is not None:
            try:
                aht10_temp, aht10_rh = self._aht10.read()
            except Exception:
                pass

        # Choose primary env for ENS160 + UI
        # Prefer AHT21 if it read, else AHT10, else 0/0
        if aht21_temp is not None and aht21_rh is not None:
            temp_c, rh = float(aht21_temp), float(aht21_rh)
            env_src = "aht21"
        elif aht10_temp is not None and aht10_rh is not None:
            temp_c, rh = float(aht10_temp), float(aht10_rh)
            env_src = "aht10"
        else:
            temp_c, rh = 0.0, 0.0
            env_src = "none"

        aqi, tvoc_ppb, eco2_ppm, ready, reason = self._read_ens160_with_retry(
            temp_c, rh, timeout_ms=4500, step_ms=250
        )

        rating = self._rating_from_aqi(aqi) if ready else "Not ready"

        conf = None
        if calculate_co2_confidence is not None:
            try:
                conf = int(calculate_co2_confidence(
                    ens_valid=bool(ready),
                    warmup_done=bool(warmup_done),
                    temp_ok=bool(self._temp_ok(temp_c)),
                    rh_ok=bool(self._rh_ok(rh)),
                    eco2_ppm=int(eco2_ppm),
                    last_eco2_ppm=self._last_eco2_ppm,
                    aqi=int(aqi) if aqi is not None else None,
                    last_aqi=self._last_aqi,
                    source=str(source),
                ))
            except Exception:
                conf = None

        # Include which env source we used in "source" if you want
        # (keeps your existing semantics but adds detail)
        source_tag = "{}".format(source)
        if env_src != "none":
            source_tag = "{}+{}".format(source_tag, env_src)

        r = AirReading(
            timestamp=self._now_timestamp(),
            temp_c=temp_c,
            humidity=rh,
            eco2_ppm=eco2_ppm,
            tvoc_ppb=tvoc_ppb,
            aqi=aqi,
            rating=rating,
            source=source_tag,
            ready=ready,
            confidence=conf,
            reason=reason,
            aht10_temp_c=aht10_temp,
            aht10_humidity=aht10_rh,
            aht21_temp_c=aht21_temp,
            aht21_humidity=aht21_rh,
        )

        if ready:
            self._last = r
            self._last_eco2_ppm = int(eco2_ppm)
            self._last_aqi = int(aqi)

        return r

    # ----------------------------
    # Warmup gating
    # ----------------------------
    def begin_sampling(self, warmup_seconds, source="button"):
        self._warmup_until = time.ticks_add(
            time.ticks_ms(), int(max(0, warmup_seconds) * 1000)
        )
        self._warmup_source = source

    def is_ready(self):
        if self._warmup_until is None:
            return True
        return time.ticks_diff(time.ticks_ms(), self._warmup_until) >= 0

    def finish_sampling(self, log=False):
        warmup_done = True
        if self._warmup_until is not None:
            warmup_done = self.is_ready()
            if not warmup_done:
                raise RuntimeError("Warmup not complete yet")

        source = self._warmup_source or "button"
        self._warmup_until = None
        self._warmup_source = None

        r = self._read_once(source=source, warmup_done=warmup_done)

        if log and r and getattr(r, "ready", False):
            self._append_log(r)

        return r

    # ----------------------------
    # Optional lightweight logging
    # ----------------------------
    def _ensure_log_header(self):
        try:
            with open(self.log_path, "r") as f:
                _ = f.readline()
        except Exception:
            try:
                with open(self.log_path, "w") as f:
                    f.write("timestamp,temp_c,humidity,eco2_ppm,tvoc_ppb,aqi,rating,source,ready,confidence,reason,aht10_temp_c,aht10_humidity,aht21_temp_c,aht21_humidity\n")
            except Exception:
                pass

    def _append_log(self, r):
        try:
            with open(self.log_path, "a") as f:
                f.write(
                    "{},{:.2f},{:.2f},{},{},{},{},{},{},{},{},{},{},{}\n".format(
                        r.timestamp, r.temp_c, r.humidity,
                        r.eco2_ppm, r.tvoc_ppb, r.aqi,
                        r.rating, r.source,
                        int(1 if r.ready else 0),
                        (r.confidence if r.confidence is not None else ""),
                        r.reason,
                        ("" if r.aht10_temp_c is None else "{:.2f}".format(float(r.aht10_temp_c))),
                        ("" if r.aht10_humidity is None else "{:.2f}".format(float(r.aht10_humidity))),
                        ("" if r.aht21_temp_c is None else "{:.2f}".format(float(r.aht21_temp_c))),
                        ("" if r.aht21_humidity is None else "{:.2f}".format(float(r.aht21_humidity))),
                    )
                )
        except Exception:
            pass

    def get_last_logged(self):
        return self._last

    def get_log_count(self):
        try:
            n = 0
            with open(self.log_path, "r") as f:
                for _ in f:
                    n += 1
            return max(0, n - 1)
        except Exception:
            return 0

    def read_quick(self, source="summary"):
        """
        Faster read intended for live UI refresh.
        Uses shorter ENS retry window and returns last_good if not ready.
        """
        try:
            self._ensure_hw()

            # AHT21 best effort
            aht21_temp, aht21_rh = None, None
            try:
                aht21_temp, aht21_rh = self._aht.read()
            except Exception:
                pass

            # AHT10 best effort
            aht10_temp, aht10_rh = None, None
            if self._aht10 is not None:
                try:
                    aht10_temp, aht10_rh = self._aht10.read()
                except Exception:
                    pass

            if aht21_temp is not None and aht21_rh is not None:
                temp_c, rh = float(aht21_temp), float(aht21_rh)
                env_src = "aht21"
            elif aht10_temp is not None and aht10_rh is not None:
                temp_c, rh = float(aht10_temp), float(aht10_rh)
                env_src = "aht10"
            else:
                temp_c, rh = 0.0, 0.0
                env_src = "none"

            aqi, tvoc_ppb, eco2_ppm, ready, reason = self._read_ens160_with_retry(
                temp_c, rh, timeout_ms=1000, step_ms=200
            )
            rating = self._rating_from_aqi(aqi) if ready else "Not ready"

            conf = 0
            try:
                from src.sensors.co2_confidence import calculate_co2_confidence as _calc
                last = self._last
                conf = _calc(
                    ens_valid=ready,
                    warmup_done=True,
                    temp_ok=True,
                    rh_ok=True,
                    eco2_ppm=int(eco2_ppm),
                    last_eco2_ppm=int(last.eco2_ppm) if last else None,
                    aqi=int(aqi),
                    last_aqi=int(last.aqi) if last else None,
                    source=source,
                )
            except Exception:
                conf = 90 if ready else 0

            source_tag = "{}".format(source)
            if env_src != "none":
                source_tag = "{}+{}".format(source_tag, env_src)

            r = AirReading(
                timestamp=self._now_timestamp(),
                temp_c=temp_c,
                humidity=rh,
                eco2_ppm=eco2_ppm,
                tvoc_ppb=tvoc_ppb,
                aqi=aqi,
                rating=rating,
                source=source_tag,
                ready=ready,
                confidence=conf,
                reason=reason,
                aht10_temp_c=aht10_temp,
                aht10_humidity=aht10_rh,
                aht21_temp_c=aht21_temp,
                aht21_humidity=aht21_rh,
            )
            if ready:
                self._last = r
                return r
            return self._last or r
        except Exception:
            return self._last
