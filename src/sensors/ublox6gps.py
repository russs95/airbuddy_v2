#src/sensors/ublox6gps.py
from machine import UART,Pin
import time

class Ublox6GPS:
    def __init__(self,uart_id=1,baud=9600,tx_pin=8,rx_pin=9,timeout=200):
        self.uart=UART(uart_id,baudrate=baud,tx=Pin(tx_pin),rx=Pin(rx_pin),timeout=timeout)

    def readline(self):
        if self.uart.any():
            return self.uart.readline()
        return None

    def read_nmea(self,max_ms=0):
        #Non-blocking: max_ms is kept for API compatibility
        if not hasattr(self,"_rxbuf"):
            self._rxbuf=b""

        #Pull whatever is available now
        try:
            n=self.uart.any()
        except:
            n=0

        if n:
            try:
                chunk=self.uart.read(n)
                if chunk:
                    self._rxbuf+=chunk
                    #prevent runaway buffer if garbage/no newlines
                    if len(self._rxbuf)>2048:
                        self._rxbuf=self._rxbuf[-1024:]
            except:
                pass

        #Extract complete lines
        while True:
            i=self._rxbuf.find(b"\n")
            if i<0:
                return None
            line=self._rxbuf[:i+1]
            self._rxbuf=self._rxbuf[i+1:]

            #Normalize line
            try:
                txt=line.decode("ascii","ignore").strip()
            except:
                txt=""

            if txt.startswith("$GP") or txt.startswith("$GN"):
                return txt


    def get_rmc(self,max_ms=2000):
        t=time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(),t)<max_ms:
            line=self.read_nmea(max_ms=300)
            if line and ("RMC" in line):
                return line
        return None

    def has_fix(self,max_ms=2000):
        rmc=self.get_rmc(max_ms=max_ms)
        if not rmc:
            return False
        parts=rmc.split(",")
        if len(parts)>2 and parts[2]=="A":
            return True
        return False

    def get_utc_datetime(self,max_ms=4000):
        """
        Returns (year,month,day,weekday,hour,minute,sec) from RMC when fix is valid.
        """
        rmc=self.get_rmc(max_ms=max_ms)
        if not rmc:
            return None
        p=rmc.split(",")
        if len(p)<10:
            return None
        if p[2]!="A":
            return None

        hhmmss=p[1]
        ddmmyy=p[9]
        if len(hhmmss)<6 or len(ddmmyy)!=6:
            return None

        hour=int(hhmmss[0:2])
        minute=int(hhmmss[2:4])
        sec=int(float(hhmmss[4:]))  # handles fractional seconds

        day=int(ddmmyy[0:2])
        month=int(ddmmyy[2:4])
        yy=int(ddmmyy[4:6])
        year=2000+yy if yy<80 else 1900+yy

        # weekday: MicroPython wants 0..6, DS3231 wants 1..7. We'll compute later if needed.
        # Here we return weekday=1 placeholder; main can compute or ignore.
        weekday=1
        return (year,month,day,weekday,hour,minute,sec)
