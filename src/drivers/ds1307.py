# src/drivers/ds1307.py
from micropython import const

_DS1307_ADDRESS = const(0x68)

def _bcd2bin(value):
    return (value & 0x0F) + ((value >> 4) * 10)

def _bin2bcd(value):
    return ((value // 10) << 4) | (value % 10)

class DS1307:
    def __init__(self, i2c, addr=_DS1307_ADDRESS):
        self.i2c = i2c
        self.addr = addr

    def datetime(self, dt=None):
        """
        Get/set datetime.
        Returns: (year, month, day, weekday, hour, minute, second, subsecond)
        weekday: 1-7 on DS1307 (we pass through)
        subsecond always 0
        """
        if dt is None:
            data = self.i2c.readfrom_mem(self.addr, 0x00, 7)
            sec = _bcd2bin(data[0] & 0x7F)
            minute = _bcd2bin(data[1])
            hour = _bcd2bin(data[2] & 0x3F)   # 24h
            wday = _bcd2bin(data[3])
            mday = _bcd2bin(data[4])
            month = _bcd2bin(data[5])
            year = 2000 + _bcd2bin(data[6])
            return (year, month, mday, wday, hour, minute, sec, 0)

        year, month, mday, wday, hour, minute, sec, _ = dt
        year = year - 2000
        buf = bytearray(7)
        buf[0] = _bin2bcd(sec)     # CH bit = 0
        buf[1] = _bin2bcd(minute)
        buf[2] = _bin2bcd(hour)    # 24h mode
        buf[3] = _bin2bcd(wday)
        buf[4] = _bin2bcd(mday)
        buf[5] = _bin2bcd(month)
        buf[6] = _bin2bcd(year)
        self.i2c.writeto_mem(self.addr, 0x00, buf)
