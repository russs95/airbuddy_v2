# src/hal/board.py
# Board facade: import this everywhere instead of hardcoding pins.

from src.hal.platform import platform_tag

_TAG = platform_tag()

if _TAG == "pico":
    from src.hal.board_pico import init_i2c, gps_pins, btn_pin, btn_led_pin
elif _TAG == "esp32":
    from src.hal.board_esp32 import init_i2c, gps_pins, btn_pin, btn_led_pin
else:
    # Conservative fallback: try ESP32-ish defaults
    from src.hal.board_esp32 import init_i2c, gps_pins, btn_pin, btn_led_pin

def tag():
    return _TAG
