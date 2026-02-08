# src/app/main.py — AirBuddy 2.1 core loop (Pico / MicroPython)

import time
from machine import Pin, I2C, RTC


# ------------------------------------------------------------
# EARLY DEBUG ESCAPE (ABSOLUTELY FIRST)
# ------------------------------------------------------------

def debug_requested_at_boot(gpio_pin=15, hold_ms=2000):
    pin = Pin(gpio_pin, Pin.IN, Pin.PULL_UP)
    start = time.ticks_ms()

    if pin.value() != 0:
        return False

    while time.ticks_diff(time.ticks_ms(), start) < hold_ms:
        if pin.value() != 0:
            return False
        time.sleep_ms(10)

    return True


if debug_requested_at_boot():
    print("=== AirBuddy DEBUG MODE ===")
    print("Button held at boot.")
    print("REPL safe mode.")
    while True:
        time.sleep(1)


# ------------------------------------------------------------
# NORMAL IMPORTS
# ------------------------------------------------------------

from src.drivers.ds3231 import DS3231
from src.input.button import AirBuddyButton
from src.ui.oled import OLED
from src.ui.booter import Booter
from src.ui.spinner import Spinner
from src.ui.waiting import WaitingScreen
from src.ui.screens.co2 import CO2Screen
from src.sensors.air import AirSensor

from src.ui.screens.time import TimeScreen
from src.app.sysinfo import get_time_str, get_date_str, get_ip_address



# ------------------------------------------------------------
# I2C (RTC BUS)
# ------------------------------------------------------------

def init_i2c_rtc():
    """
    DS3231 is wired to:
      SDA -> GPIO0
      SCL -> GPIO1
    That's I2C(0) on the Pico.
    """
    i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    print("RTC SDA/SCL raw:",
          Pin(0, Pin.IN, Pin.PULL_UP).value(),
          Pin(1, Pin.IN, Pin.PULL_UP).value())
    print("RTC I2C scan:", [hex(x) for x in i2c.scan()])
    return i2c


def try_sync_system_rtc_from_ds3231(i2c):
    """
    Attempts to sync the Pico system RTC from DS3231.
    Returns True if synced, False if not (missing, OSF set, etc.)
    """
    try:
        ds = DS3231(i2c)

        if ds.lost_power():
            # OSF means oscillator stopped at some point; time might be garbage.
            print("RTC: DS3231 OSF set (time not trusted).")
            return False

        year, month, day, weekday, hour, minute, sec = ds.datetime()

        # DS3231 weekday: 1..7 (Mon..Sun)
        # MicroPython RTC weekday: typically 0..6
        wd0 = (weekday - 1) % 7

        RTC().datetime((year, month, day, wd0, hour, minute, sec, 0))
        print("RTC: system clock synced from DS3231:", (year, month, day, hour, minute, sec))
        return True

    except Exception as e:
        print("RTC: sync attempt failed:", repr(e))
        return False


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------

def run(rtc_synced=False):
    oled = OLED()

    # ----------------------------
    # RTC STATUS (DS3231 + system time)
    # ----------------------------
    rtc_i2c = init_i2c_rtc()

    ds3231 = None
    ds3231_ok = False
    ds3231_osf = False
    ds3231_temp = None

    try:
        ds3231 = DS3231(rtc_i2c)
        ds3231_ok = True
        ds3231_osf = ds3231.lost_power()
        try:
            ds3231_temp = ds3231.temperature()
        except Exception:
            ds3231_temp = None
        print("DS3231 OK:", ds3231.datetime(), "OSF=", ds3231_osf, "TEMP=", ds3231_temp)
    except Exception as e:
        print("DS3231 missing:", repr(e))

    # If root main.py didn't sync, we can try once here (safe).
    if (not rtc_synced) and ds3231_ok:
        rtc_synced = try_sync_system_rtc_from_ds3231(rtc_i2c)

    # ----------------------------
    # INIT CORE OBJECTS
    # ----------------------------
    btn = AirBuddyButton(gpio_pin=15)
    spinner = Spinner(oled)
    waiting = WaitingScreen()
    co2_screen = CO2Screen(oled)
    time_screen = TimeScreen(oled)
    air = AirSensor()

    # ----------------------------
    # BOOT + SENSOR WARMUP (ONCE)
    # ----------------------------
    warmup_s = 4.0
    air.begin_sampling(warmup_seconds=warmup_s, source="boot")
    Booter(oled).show(duration=warmup_s, fps=18)

    # ----------------------------
    # MAIN LOOP
    # ----------------------------
    while True:

        # ----------------------------
        # IDLE (STATIC — NO ANIMATION)
        # ----------------------------
        waiting.show(oled, line="Know your air", animate=False)

        action = btn.wait_for_action()

        # ----------------------------
        # DEBUG
        # ----------------------------
        if action == "debug":
            waiting.show(oled, line="Debug mode", animate=False)
            while True:
                time.sleep(1)

        # ----------------------------
        # TIME / CLOCK INFO (double click)
        # ----------------------------
        if action == "double":
            date_str = get_date_str()
            time_str = get_time_str()

            # Refresh temp live
            temp_c = None
            if ds3231_ok and ds3231:
                try:
                    temp_c = ds3231.temperature()
                    ds3231_osf = ds3231.lost_power()  # refresh OSF too
                except Exception:
                    temp_c = None

            source = "RTC" if (rtc_synced and ds3231_ok and (not ds3231_osf)) else "SYS"

            time_screen.show(
                date_str=date_str,
                time_str=time_str,
                source=source,
                temp_c=temp_c
            )
            time.sleep(4)
            continue

        # ----------------------------
        # SAMPLING (single click)
        # ----------------------------
        cached = False

        try:
            # 1️⃣ Cosmetic spinner ONLY (exactly 3 seconds)
            spinner.spin(duration=3.0)

            # 2️⃣ Read sensor AFTER spinner
            reading = air.finish_sampling(log=False)

            if getattr(reading, "source", "") == "fallback":
                cached = True

        except Exception as e:
            print("[MAIN] sampling failed:", repr(e))
            last = air.get_last_logged()
            if last is None:
                waiting.show(oled, line="Sensor error", animate=False)
                time.sleep(3)
                continue
            reading = last
            cached = True

        # ----------------------------
        # DISPLAY CO₂ SCREEN (10s)
        # ----------------------------
        confidence = 70 if cached else 92
        co2_screen.show(reading, confidence_pct=confidence)
        time.sleep(10)

# ------------------------------------------------------------
# ENTRY POINT (DO NOT CALL run() ANYWHERE ELSE)
# ------------------------------------------------------------

if __name__ == "__main__":
    # Backward-compatible direct run
    run(rtc_synced=False)
