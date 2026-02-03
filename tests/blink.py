from machine import Pin
import time

# Common LED pins on some ESP32 dev boards: 2, 4, 5
# We'll just try one; if no LED, you can wire an LED + resistor to a known pin.
LED_PIN = 2

led = Pin(LED_PIN, Pin.OUT)
while True:
    led.value(1)
    time.sleep(0.2)
    led.value(0)
    time.sleep(0.2)
