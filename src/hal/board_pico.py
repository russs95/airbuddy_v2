# src/hal/board_pico.py
# Pico / Pico W pin map + common initializers.

from machine import Pin, I2C

# I2C for OLED + DS3231 on your Pico wiring
I2C_ID = 0
I2C_SCL = 1
I2C_SDA = 0
I2C_FREQ = 400_000

# GPS defaults (your existing Pico values)
GPS_UART_ID = 1
GPS_BAUD = 9600
GPS_TX_PIN = 8
GPS_RX_PIN = 9

def init_i2c():
    return I2C(I2C_ID, scl=Pin(I2C_SCL), sda=Pin(I2C_SDA), freq=I2C_FREQ)

def gps_pins():
    return GPS_UART_ID, GPS_BAUD, GPS_TX_PIN, GPS_RX_PIN
