from machine import Pin
import time

RST = Pin(15, Pin.OUT)
BUSY = Pin(4, Pin.IN)

print("Initial BUSY:", BUSY.value())

# Pulse reset a few times and watch BUSY
for i in range(5):
    RST.value(0)
    time.sleep_ms(10)
    RST.value(1)
    time.sleep_ms(200)
    print("BUSY after reset", i, ":", BUSY.value())
    time.sleep(1)
