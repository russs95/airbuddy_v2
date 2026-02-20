# src/sensors/ublox6gps.py
from machine import UART, Pin
import time


class Ublox6GPS:
    def __init__(
            self,
            uart_id=None,
            baud=9600,
            tx_pin=None,
            rx_pin=None,
            timeout=200,
    ):
        """
        Portable GPS driver.
        If pins not provided, pulls from src.hal.board.gps_pins()
        """

        # Pull from HAL if not explicitly provided
        if uart_id is None or tx_pin is None or rx_pin is None:
            try:
                from src.hal.board import gps_pins
                _uart_id, _tx, _rx = gps_pins()

                if uart_id is None:
                    uart_id = _uart_id
                if tx_pin is None:
                    tx_pin = _tx
                if rx_pin is None:
                    rx_pin = _rx
            except Exception:
                # Pico fallback defaults
                if uart_id is None:
                    uart_id = 1
                if tx_pin is None:
                    tx_pin = 8
                if rx_pin is None:
                    rx_pin = 9

        self.uart = UART(
            int(uart_id),
            baudrate=int(baud),
            tx=Pin(int(tx_pin)),
            rx=Pin(int(rx_pin)),
            timeout=timeout,
        )

        self._rxbuf = b""

    # -------------------------------------------------
    # Non-blocking line read
    # -------------------------------------------------
    def readline(self):
        if self.uart.any():
            return self.uart.readline()
        return None

    def read_nmea(self, max_ms=0):
        # Pull whatever is available
        try:
            n = self.uart.any()
        except:
            n = 0

        if n:
            try:
                chunk = self.uart.read(n)
                if chunk:
                    self._rxbuf += chunk
                    # prevent runaway buffer
                    if len(self._rxbuf) > 2048:
                        self._rxbuf = self._rxbuf[-1024:]
            except:
                pass

        # Extract full lines
        while True:
            i = self._rxbuf.find(b"\n")
            if i < 0:
                return None

            line = self._rxbuf[:i + 1]
            self._rxbuf = self._rxbuf[i + 1:]

            try:
                txt = line.decode("ascii", "ignore").strip()
            except:
                txt = ""

            if txt.startswith("$GP") or txt.startswith("$GN"):
                return txt

    # -------------------------------------------------
    # RMC helpers
    # -------------------------------------------------
    def get_rmc(self, max_ms=2000):
        t = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t) < max_ms:
            line = self.read_nmea()
            if line and ("RMC" in line):
                return line
        return None

    def has_fix(self, max_ms=2000):
        rmc = self.get_rmc(max_ms=max_ms)
        if not rmc:
            return False
        parts = rmc.split(",")
        return len(parts) > 2 and parts[2] == "A"

    def get_utc_datetime(self, max_ms=4000):
        """
        Returns (year,month,day,weekday,hour,minute,sec)
        """
        rmc = self.get_rmc(max_ms=max_ms)
        if not rmc:
            return None

        p = rmc.split(",")
        if len(p) < 10:
            return None
        if p[2] != "A":
            return None

        hhmmss = p[1]
        ddmmyy = p[9]
        if len(hhmmss) < 6 or len(ddmmyy) != 6:
            return None

        hour = int(hhmmss[0:2])
        minute = int(hhmmss[2:4])
        sec = int(float(hhmmss[4:]))

        day = int(ddmmyy[0:2])
        month = int(ddmmyy[2:4])
        yy = int(ddmmyy[4:6])
        year = 2000 + yy if yy < 80 else 1900 + yy

        weekday = 1  # placeholder
        return (year, month, day, weekday, hour, minute, sec)
