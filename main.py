# main.py (device root) — AirBuddy 2.1 launcher + RTC sync

from machine import Pin, I2C, RTC


def sync_rtc_from_ds3231():
    """
    Sync MicroPython system RTC from DS3231 (I2C0: SDA=GPIO0, SCL=GPIO1).

    Returns:
        True  -> successfully synced system time from DS3231
        False -> DS3231 missing, unreachable, or reports oscillator stop (time unreliable)
    """
    try:
        # I2C0 on Pico: SDA=GP0, SCL=GP1
        i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

        # Import here so boot still works even if driver missing
        from src.drivers.ds3231 import DS3231
        ds = DS3231(i2c)

        # If OSF is set, DS3231 time may be invalid (battery/power loss).
        # Don't overwrite system RTC with bad time.
        if ds.lost_power():
            print("RTC: DS3231 oscillator-stop flag set (time not trusted).")
            return False

        year, month, day, weekday, hour, minute, sec = ds.datetime()

        # MicroPython RTC datetime format:
        # (year, month, day, weekday, hours, minutes, seconds, subseconds)
        # DS3231 weekday is 1..7 (Mon..Sun). Convert to 0..6.
        wd0 = (weekday - 1) % 7

        RTC().datetime((year, month, day, wd0, hour, minute, sec, 0))
        print("RTC: synced from DS3231:", (year, month, day, hour, minute, sec))
        return True

    except Exception as e:
        print("RTC: sync failed:", repr(e))
        return False


# ---- Boot sequence ----
rtc_synced = sync_rtc_from_ds3231()

try:
    from src.app.main import run
    # Pass flag so app can decide whether to prompt user to set time
    run(rtc_synced=rtc_synced)
except TypeError:
    # Backward compatibility if your run() doesn't accept args yet
    from src.app.main import run
    run()
except Exception as e:
    # Always print something helpful in REPL if boot fails
    print("AirBuddy boot error:", repr(e))
    raise
