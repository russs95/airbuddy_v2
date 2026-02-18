# src/hal/board_esp32.py
# ESP32 pin map + common initializers.

from machine import Pin, I2C

# Standard ESP32 I2C pins (safe, common)
I2C_ID = 0
I2C_SCL = 22
I2C_SDA = 21
I2C_FREQ = 400_000

# IMPORTANT: avoid GPIO 6-11 (flash pins). Your old GPS pins 8/9 are unsafe on ESP32.
GPS_UART_ID = 2
GPS_BAUD = 9600
GPS_TX_PIN = 17
GPS_RX_PIN = 16

def init_i2c():
    return I2C(I2C_ID, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)

def gps_pins():
    return GPS_UART_ID, GPS_BAUD, GPS_TX_PIN, GPS_RX_PIN
