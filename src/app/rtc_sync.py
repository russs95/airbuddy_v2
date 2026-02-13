#src/app/rtc_sync.py

import time
from machine import RTC
from src.drivers.ds3231 import DS3231

def ds3231_seconds_ticking(ds,sample_ms=1200):
    try:
        t1=ds.datetime()
        s1=int(t1[6])
        time.sleep_ms(int(sample_ms))
        t2=ds.datetime()
        s2=int(t2[6])
        return s2!=s1
    except:
        return False

def sync_system_rtc_from_ds3231(i2c,min_year=2024):
    """
    Returns dict:
      ok: DS3231 present
      synced: system RTC set from DS3231
      sane: DS3231 time looked sane
      osf: oscillator stop flag set
      ticking: seconds change observed
      dt: (year,month,day,weekday,hour,minute,sec) or None
      temp_c: float or None
    """
    out={"ok":False,"synced":False,"sane":False,"osf":False,"ticking":False,"dt":None,"temp_c":None}
    try:
        ds=DS3231(i2c)
        out["ok"]=True
        dt=ds.datetime()
        out["dt"]=dt
        try:
            out["temp_c"]=ds.temperature()
        except:
            out["temp_c"]=None

        year,month,day,weekday,hour,minute,sec=dt
        sane=(year>=min_year and 1<=month<=12 and 1<=day<=31)
        out["sane"]=sane

        try:
            osf=bool(ds.lost_power())
        except:
            osf=False
        out["osf"]=osf

        ticking=ds3231_seconds_ticking(ds)
        out["ticking"]=ticking

        #Auto-clear OSF if ticking
        if osf and ticking:
            try:
                ds.clear_lost_power()
                out["osf"]=bool(ds.lost_power())
            except:
                pass

        if not sane:
            return out

        wd0=(weekday-1)%7
        RTC().datetime((year,month,day,wd0,hour,minute,sec,0))
        out["synced"]=True
        return out

    except Exception:
        return out
