# src/sensors/air.py  (MicroPython / Pico W)  — Pico-safe (no dataclasses, no PEP604 unions)
import time
from machine import Pin, I2C


class AirReading:
    """
    Lightweight reading container (Pico-safe).
    """
    def __init__(self, timestamp, temp_c, humidity, eco2_ppm, tvoc_ppb, aqi, rating, source):
        self.timestamp = int(timestamp)
        self.temp_c = float(temp_c)
        self.humidity = float(humidity)
        self.eco2_ppm = int(eco2_ppm)
        self.tvoc_ppb = int(tvoc_ppb)
        self.aqi = int(aqi)
        self.rating = str(rating)
        self.source = str(source)


# ----------------------------
# Minimal AHT21 driver
# ----------------------------
class AHT21:
    def __init__(self, i2c, addr=0x38):
        self.i2c = i2c
        self.addr = addr

    def read(self):
        # Trigger measurement
        self.i2c.writeto(self.addr, b"\xAC\x33\x00")
        time.sleep_ms(85)

        data = self.i2c.readfrom(self.addr, 6)

        # 20-bit humidity and temperature
        raw_h = ((data[1] << 12) | (data[2] << 4) | (data[3] >> 4)) & 0xFFFFF
        raw_t = (((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5]) & 0xFFFFF

        humidity = raw_h * 100.0 / 1048576.0
        temp_c = raw_t * 200.0 / 1048576.0 - 50.0
        return temp_c, humidity


# ----------------------------
# Minimal ENS160 driver
# ----------------------------
class ENS160:
    # Common registers
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
        # Read part id (sanity check / smoke test)
        _ = self._read(self._REG_PART_ID, 2)

        # Set standard operation mode
        self._write8(self._REG_OPMODE, self._OPMODE_STD)
        time.sleep_ms(50)

    def set_environment(self, temp_c, rh):
        # Datasheet style scaling:
        # temp in Kelvin * 64, humidity in %RH * 512
        temp_k = float(temp_c) + 273.15
        tval = int(temp_k * 64)
        hval = int(float(rh) * 512)
        self._write16(self._REG_TEMP_IN, tval)
        self._write16(self._REG_RH_IN, hval)

    def read_air(self):
        aqi = self._read(self._REG_DATA_AQI, 1)[0]
        tvoc = self._read(self._REG_DATA_TVOC, 2)
        eco2 = self._read(self._REG_DATA_ECO2, 2)
        tvoc_ppb = tvoc[0] | (tvoc[1] << 8)
        eco2_ppm = eco2[0] | (eco2[1] << 8)
        return aqi, tvoc_ppb, eco2_ppm


class AirSensor:
    """
    MicroPython AirSensor (Pico W):
      - ENS160 + AHT21 read
      - begin_sampling()/finish_sampling() warmup support (for spinner)
      - optional lightweight CSV logging (disabled by default)

    NOTE: No background scheduler/threading in v2.1.
    """

    def __init__(
            self,
            i2c_id=0,
            pin_sda=0,
            pin_scl=1,
            freq=100_000,
            oled_addr=0x3C,     # not used, but handy for scan sanity
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

        # Keep last successful reading in RAM (fast fallback)
        self._last = None

        # Create log file header if logging is used
        self._ensure_log_header()

    # ----------------------------
    # Rating
    # ----------------------------
    @staticmethod
    def _rating_from_aqi(aqi):
        # ENS160 AQI: 1 Excellent .. 5 Unhealthy
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
        # If RTC/NTP not set, this may be "seconds since 2000-ish" or uptimeish.
        # Still useful for ordering.
        try:
            return int(time.time())
        except Exception:
            return 0

    # ----------------------------
    # Core read
    # ----------------------------
    def _read_once(self, source):
        temp_c, rh = self._aht.read()

        # Temperature/humidity compensation
        try:
            self._ens.set_environment(temp_c, rh)
        except Exception:
            pass

        aqi, tvoc_ppb, eco2_ppm = self._ens.read_air()
        rating = self._rating_from_aqi(aqi)

        r = AirReading(
            timestamp=self._now_timestamp(),
            temp_c=temp_c,
            humidity=rh,
            eco2_ppm=eco2_ppm,
            tvoc_ppb=tvoc_ppb,
            aqi=aqi,
            rating=rating,
            source=source,
        )
        self._last = r
        return r

    # ----------------------------
    # Non-blocking warmup
    # ----------------------------
    def begin_sampling(self, warmup_seconds, source="button"):
        self._warmup_until = time.ticks_add(time.ticks_ms(), int(max(0, warmup_seconds) * 1000))
        self._warmup_source = source

    def is_ready(self):
        if self._warmup_until is None:
            return True
        return time.ticks_diff(time.ticks_ms(), self._warmup_until) >= 0

    def finish_sampling(self, log=False):
        if self._warmup_until is not None and not self.is_ready():
            raise RuntimeError("Warmup not complete yet")

        source = self._warmup_source or "button"
        self._warmup_until = None
        self._warmup_source = None

        try:
            r = self._read_once(source=source)
            if log:
                self._append_log(r)
            return r
        except Exception as e:
            # Fallback to last known good reading if we have one
            if self._last is not None:
                return AirReading(
                    timestamp=self._now_timestamp(),
                    temp_c=self._last.temp_c,
                    humidity=self._last.humidity,
                    eco2_ppm=self._last.eco2_ppm,
                    tvoc_ppb=self._last.tvoc_ppb,
                    aqi=self._last.aqi,
                    rating=self._last.rating,
                    source="fallback",
                )
            raise e

    # ----------------------------
    # Optional lightweight logging
    # ----------------------------
    def _ensure_log_header(self):
        try:
            # If file doesn't exist, this will throw
            with open(self.log_path, "r") as f:
                _ = f.readline()
        except Exception:
            try:
                with open(self.log_path, "w") as f:
                    f.write("timestamp,temp_c,humidity,eco2_ppm,tvoc_ppb,aqi,rating,source\n")
            except Exception:
                # Logging is optional; don't fail boot
                pass

    def _append_log(self, r):
        try:
            with open(self.log_path, "a") as f:
                f.write(
                    "{},{:.2f},{:.2f},{},{},{},{},{}\n".format(
                        r.timestamp, r.temp_c, r.humidity, r.eco2_ppm, r.tvoc_ppb, r.aqi, r.rating, r.source
                    )
                )
        except Exception:
            pass

    def get_last_logged(self):
        # For v2.1, prefer in-RAM last; file parsing is optional and slow.
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
