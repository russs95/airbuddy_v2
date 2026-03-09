# src/hal/board_esp32.py
# ESP32 pin map + common initializers.

from machine import Pin, I2C

# ------------------------------------------------------------
# Button (AirBuddy)
# ------------------------------------------------------------
# Recommended wiring (safer than strapping pins):
#   - GPIO4  -> button signal (use internal pull-up)
#   - GND    -> button ground
#
# Optional button LED:
#   - GPIO18 -> LED + resistor -> GND   (active-high)
# ------------------------------------------------------------

BTN_PIN = 4
BTN_LED_PIN = 18  # change if needed

def btn_pin():
    return BTN_PIN

def btn_led_pin():
    return BTN_LED_PIN


# ------------------------------------------------------------
# I2C (OLED + DS3231 + sensors)
# ------------------------------------------------------------
# Common ESP32 I2C pins
I2C_ID = 0
I2C_SCL = 22
I2C_SDA = 21
I2C_FREQ = 400_000

def init_i2c():
    return I2C(I2C_ID, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)

def i2c_pins():
    # (i2c_id, scl, sda, freq)
    return (I2C_ID, I2C_SCL, I2C_SDA, I2C_FREQ)


# ------------------------------------------------------------
# GPS (Ublox)
# ------------------------------------------------------------
GPS_UART_ID = 2
GPS_BAUD = 9600
GPS_TX_PIN = 17
GPS_RX_PIN = 16

def gps_pins():
    return (GPS_UART_ID, GPS_BAUD, GPS_TX_PIN, GPS_RX_PIN)