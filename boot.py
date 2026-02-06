# boot.py  (Pico / MicroPython)
import time
from machine import Pin

# Hold GP15 button for 2s during boot to skip running main/app code.
BTN = Pin(15, Pin.IN, Pin.PULL_UP)

def held_low(ms):
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < ms:
        if BTN.value() != 0:
            return False
        time.sleep_ms(10)
    return True

# If button is held at power-up, create a "debug flag" file and do NOT auto-run app.
if BTN.value() == 0 and held_low(2000):
    try:
        with open("DEBUG_MODE", "w") as f:
            f.write("1")
    except Exception:
        pass
