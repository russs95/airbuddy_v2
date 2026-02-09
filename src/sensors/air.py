# src/sensors/air.py  (MicroPython / Pico W) — Pico-safe
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
            reason=""
    ):
        self.timestamp = int(timestamp)
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


# ----------------------------
# Minimal AHT21 driver
# ----------------------------
class AHT21:
    def __init__(self, i2c, addr=0x38):
        self.i2c = i2c
        self.addr = addr

    def read(self):
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
    _REG_PART_ID   = 0x00
    _REG_OPMODE    = 0x10
    _REG_TEMP_IN   = 0x13
    _REG_RH_IN     = 0x15
    _REG_DATA_AQI  = 0x21
    _REG_DATA_TVOC = 0x22
    _REG_DATA_ECO2 = 0x24

    _OPMODE_STD    = 0x02

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
      - ENS160 + AHT21 read
      - begin_sampling()/finish_sampling() warmup timer (cosmetic / gating)
      - ENS160 retry loop so you don't get stuck with 0ppm
      - confidence score attached to AirReading.confidence
    """

    def __init__(
            self,
            i2c_id=0,
            pin_sda=0,
            pin_scl=1,
            freq=100_000,
            aht21_addr=0x38,
            ens160_addr=0x53,
            log_path="air_records.csv",
    ):
        self.log_path = log_path
        self._i2c = I2C(i2c_id, sda=Pin(pin_sda), scl=Pin(pin_scl), freq=freq)

        self._aht = AHT21(self._i2c, addr=aht21_addr)
        self._ens = ENS160(self._i2c, addr=ens160_addr)

        self._warmup_until = None
        self._warmup_source = None

        self._last = None  # last good reading (ready=True)
        self._last_eco2_ppm = None
        self._last_aqi = None

        self._ensure_log_header()

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
        # generous sensor-safe range
        return (-10.0 <= float(temp_c) <= 60.0)

    @staticmethod
    def _rh_ok(rh):
        return (0.0 <= float(rh) <= 100.0)

    # ----------------------------
    # Core read
    # ----------------------------
    def _read_once(self, source, warmup_done):
        temp_c, rh = self._aht.read()

        aqi, tvoc_ppb, eco2_ppm, ready, reason = self._read_ens160_with_retry(
            temp_c, rh, timeout_ms=4500, step_ms=250
        )

        rating = self._rating_from_aqi(aqi) if ready else "Not ready"

        # Confidence (from your model)
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

        r = AirReading(
            timestamp=self._now_timestamp(),
            temp_c=temp_c,
            humidity=rh,
            eco2_ppm=eco2_ppm,
            tvoc_ppb=tvoc_ppb,
            aqi=aqi,
            rating=rating,
            source=source,
            ready=ready,
            confidence=conf,
            reason=reason
        )

        # Update last-good trackers (for stability confidence)
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
        # allow calling without begin_sampling()
        warmup_done = True
        if self._warmup_until is not None:
            warmup_done = self.is_ready()
            if not warmup_done:
                raise RuntimeError("Warmup not complete yet")

        source = self._warmup_source or "button"
        self._warmup_until = None
        self._warmup_source = None

        r = self._read_once(source=source, warmup_done=warmup_done)

        if log and r.ready:
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
                    f.write("timestamp,temp_c,humidity,eco2_ppm,tvoc_ppb,aqi,rating,source,ready,confidence,reason\n")
            except Exception:
                pass

    def _append_log(self, r):
        try:
            with open(self.log_path, "a") as f:
                f.write(
                    "{},{:.2f},{:.2f},{},{},{},{},{},{},{},{}\n".format(
                        r.timestamp, r.temp_c, r.humidity,
                        r.eco2_ppm, r.tvoc_ppb, r.aqi,
                        r.rating, r.source,
                        int(1 if r.ready else 0),
                        (r.confidence if r.confidence is not None else ""),
                        r.reason
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
