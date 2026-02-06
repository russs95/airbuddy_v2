# src/app/main.py — AirBuddy 2.1 core loop (Pico / MicroPython)

import time
from machine import Pin


# ------------------------------------------------------------
# EARLY DEBUG ESCAPE (ABSOLUTELY FIRST)
# ------------------------------------------------------------

def debug_requested_at_boot(gpio_pin=15, hold_ms=2000) -> bool:
    pin = Pin(gpio_pin, Pin.IN, Pin.PULL_UP)
    start = time.ticks_ms()

    if pin.value() != 0:
        return False

    while time.ticks_diff(time.ticks_ms(), start) < int(hold_ms):
        if pin.value() != 0:
            return False
        time.sleep_ms(10)

    return True


if debug_requested_at_boot(gpio_pin=15, hold_ms=2000):
    print("=== AirBuddy DEBUG MODE ===")
    print("Button held at boot (>= 2s).")
    print("No peripherals started. REPL is safe.")
    print("Release button and reset to boot normally.")
    while True:
        time.sleep(1)


# ------------------------------------------------------------
# NORMAL IMPORTS (SAFE AFTER DEBUG CHECK)
# ------------------------------------------------------------

from src.input.button import AirBuddyButton
from src.ui.oled import OLED
from src.ui.spinner import Spinner
from src.ui.booter import Booter
from src.sensors.air import AirSensor

from src.app.sysinfo import get_time_str, get_ip_address


def create_display():
    return OLED()


def _debug_loop(oled=None, msg="Debug mode"):
    try:
        if oled:
            oled.show_waiting(msg)
    except Exception:
        pass

    print("[DEBUG] Entered debug loop. Reset to exit.")
    while True:
        time.sleep(1)


def run():
    oled = create_display()

    # Boot loader (visual only)
    Booter(oled).show(duration=2.0, fps=12)

    spinner = Spinner(oled)
    btn = AirBuddyButton(gpio_pin=15)
    air = AirSensor()

    while True:
        # ----------------------------
        # IDLE
        # ----------------------------
        oled.show_waiting("Know your air...")

        action = btn.wait_for_action()
        time.sleep(0.08)  # debounce cushion

        # ----------------------------
        # DEBUG REQUEST (long press)
        # ----------------------------
        if action == "debug":
            _debug_loop(oled, msg="Debug mode")

        # ----------------------------
        # SETTINGS (double click)
        # ----------------------------
        if action == "double":
            time_str = get_time_str()
            ip = get_ip_address()
            power_tag = "USB"

            oled.show_settings(time_str, ip, power_tag)
            time.sleep(4)
            oled.clear()
            continue

        # ----------------------------
        # CACHED LOG VIEW (triple click)
        # ----------------------------
        if action == "triple":
            last = air.get_last_logged() if hasattr(air, "get_last_logged") else None
            if last:
                log_count = air.get_log_count() if hasattr(air, "get_log_count") else 0
                oled.show_cached(last, log_count)
                time.sleep(6)
            oled.clear()
            continue

        # ----------------------------
        # SAMPLING (single click)
        # ----------------------------
        cached = False
        reading = None

        try:
            warm = 6
            air.begin_sampling(warmup_seconds=warm, source="button")
            spinner.spin(duration=warm)
            reading = air.finish_sampling(log=False)

            if getattr(reading, "source", "") == "fallback":
                cached = True

        except Exception as e:
            print("[MAIN] sampling failed:", repr(e))
            last = air.get_last_logged() if hasattr(air, "get_last_logged") else None
            if last is None:
                oled.show_waiting("Sensor error")
                time.sleep(3)
                oled.clear()
                continue
            reading = last
            cached = True

        # ----------------------------
        # DISPLAY SEQUENCE
        # ----------------------------
        tag = "cached" if cached else "just now"

        oled.show_metric("Temperature", "{:.1f}C".format(reading.temp_c), tag=tag)
        time.sleep(2)

        oled.show_metric("Humidity", "{:.0f}%".format(reading.humidity), tag=tag)
        time.sleep(2)

        oled.show_metric("eCO2 (ppm)", "{}".format(reading.eco2_ppm), tag=tag)
        time.sleep(2)

        oled.show_metric("TVOC (ppb)", "{}".format(reading.tvoc_ppb), tag=tag)
        time.sleep(2)

        oled.show_metric("AQI", "{}".format(reading.aqi), tag=tag)
        time.sleep(2)

        if hasattr(oled, "show_face") and hasattr(reading, "rating"):
            oled.show_face(reading.rating)
            time.sleep(2)

        oled.clear()


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print("[FATAL] main.py crashed:", repr(e))
        _debug_loop(None, msg="Crash")
