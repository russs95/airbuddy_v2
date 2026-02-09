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
from src.ui.screens.tvoc import TVOCScreen
from src.ui.screens.temp import TempScreen
from src.ui.screens.time import TimeScreen
from src.sensors.air import AirSensor

from src.app.sysinfo import get_time_str, get_date_str, get_ip_address
from src.ui.screens.summary import SummaryScreen


# ------------------------------------------------------------
# I2C (RTC BUS)
# ------------------------------------------------------------

def init_i2c_rtc():
    """
    DS3231 + OLED + sensors on:
      SDA -> GPIO0
      SCL -> GPIO1
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
            print("RTC: DS3231 OSF set (time not trusted).")
            return False

        year, month, day, weekday, hour, minute, sec = ds.datetime()
        wd0 = (weekday - 1) % 7

        RTC().datetime((year, month, day, wd0, hour, minute, sec, 0))
        print("RTC: system clock synced from DS3231:", (year, month, day, hour, minute, sec))
        return True

    except Exception as e:
        print("RTC: sync attempt failed:", repr(e))
        return False


# ------------------------------------------------------------
# Button helpers (local, no changes needed to button.py)
# ------------------------------------------------------------

def wait_for_any_press(btn, debounce_ms=60):
    """
    Blocks until a button press + release occurs.
    Used to advance between screens (CO2 -> TVOC -> TEMP).
    """
    # wait for press
    while btn.pin.value() == 1:
        time.sleep_ms(10)
    time.sleep_ms(debounce_ms)

    # wait for release
    while btn.pin.value() == 0:
        time.sleep_ms(10)
    time.sleep_ms(debounce_ms)


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

    try:
        ds3231 = DS3231(rtc_i2c)
        ds3231_ok = True
        ds3231_osf = ds3231.lost_power()
        print("DS3231 OK:", ds3231.datetime(), "OSF=", ds3231_osf, "TEMP=", ds3231.temperature())
    except Exception as e:
        print("DS3231 missing:", repr(e))

    if (not rtc_synced) and ds3231_ok:
        rtc_synced = try_sync_system_rtc_from_ds3231(rtc_i2c)

    # ----------------------------
    # INIT CORE OBJECTS
    # ----------------------------
    btn = AirBuddyButton(gpio_pin=15)
    spinner = Spinner(oled)
    waiting = WaitingScreen()
    co2_screen = CO2Screen(oled)
    tvoc_screen = TVOCScreen(oled)
    temp_screen = TempScreen(oled)
    time_screen = TimeScreen(oled)
    air = AirSensor()
    summary_screen = SummaryScreen(oled)


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

        # IDLE
        waiting.show(oled, line="Know your air", animate=False)

        action = btn.wait_for_action()

        # DEBUG
        if action == "debug":
            waiting.show(oled, line="Debug mode", animate=False)
            while True:
                time.sleep(1)

        # TIME / CLOCK (double click)
        if action == "double":
            def _date():
                return get_date_str()

            def _time():
                return get_time_str()

            def _source():
                return "RTC" if (rtc_synced and ds3231_ok and (not ds3231_osf)) else "SYS"

            def _temp():
                if ds3231_ok and ds3231:
                    try:
                        return ds3231.temperature()
                    except Exception:
                        return None
                return None

            time_screen.show_live(
                get_date_str=_date,
                get_time_str=_time,
                get_source=_source,
                get_temp_c=_temp,
                btn=btn,
                max_seconds=0,
                blink_ms=500,
                refresh_every_blinks=2
            )
            continue

        # Only sample on single click
        if action != "single":
            continue

        cached = False

        try:
            # Spinner (cosmetic)
            spinner.spin(duration=3.0)

            # Read sensor
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
        # Screen sequence (advance by button press)
        # ----------------------------

        # 1) CO2
        co2_screen.show(reading)
        wait_for_any_press(btn)

        # 2) TVOC
        tvoc_screen.show(reading)
        wait_for_any_press(btn)

        # 3) TEMP (with RTC temp)
        rtc_temp = None
        if ds3231_ok and ds3231:
            try:
                rtc_temp = ds3231.temperature()
            except Exception:
                rtc_temp = None

        temp_screen.show(reading, rtc_temp_c=rtc_temp)
        wait_for_any_press(btn)

        # 4) SUMMARY
        summary_screen.show(reading)
        wait_for_any_press(btn)


# back to waiting (loop continues)


if __name__ == "__main__":
    run(rtc_synced=False)
