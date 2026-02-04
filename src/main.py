# main.py


from machine import Pin, SPI
import time

from lib.epd2in13 import EPD
from fonts import font24
from button import Button

PIN_BUTTON = 27

# ---------------- Pins (ESP32) ----------------
PIN_CS   = 5
PIN_DC   = 2
PIN_RST  = 15
PIN_BUSY = 4
PIN_MOSI = 23
PIN_SCK  = 18
PIN_MISO = 19

def log(*args):
    print(*args)

def make_spi():
    return SPI(
        2,
        baudrate=2_000_000,
        polarity=0,
        phase=0,
        sck=Pin(PIN_SCK),
        mosi=Pin(PIN_MOSI),
        miso=Pin(PIN_MISO),
    )

def make_epd(spi):
    busy = Pin(PIN_BUSY, Pin.IN, Pin.PULL_UP)
    return EPD(
        spi,
        cs=Pin(PIN_CS, Pin.OUT, value=1),
        dc=Pin(PIN_DC, Pin.OUT, value=0),
        rst=Pin(PIN_RST, Pin.OUT, value=1),
        busy=busy,
    )

def alloc_framebuffer(epd):
    row_bytes = (epd.width + 7) // 8
    return bytearray(row_bytes * epd.height)

def clear_white(buf):
    for i in range(len(buf)):
        buf[i] = 0xFF

def clear_black(buf):
    for i in range(len(buf)):
        buf[i] = 0x00

def draw_centered_lines(epd, buf, lines, font):
    line_h = font.height
    total_h = len(lines) * line_h
    y = max(0, (epd.height - total_h) // 2)

    for line in lines:
        text_w = len(line) * font.width
        x = max(0, (epd.width - text_w) // 2)
        epd.display_string_at(buf, x, y, line, font, colored=1)
        y += line_h

def run_display_demo():
    log("AirBuddy: running display demo...")

    spi = make_spi()
    epd = make_epd(spi)

    log("Initializing EPD...")
    epd.init()
    log("Init OK")
    log("Resolution:", epd.width, "x", epd.height)

    buf = alloc_framebuffer(epd)

    clear_white(buf)
    epd.display_frame(buf, None)
    time.sleep(1)

    clear_black(buf)
    epd.display_frame(buf, None)
    time.sleep(1)

    clear_white(buf)
    draw_centered_lines(epd, buf, ["HELLO", "ROBBIE", "!"], font24)

    log("Refreshing display...")
    epd.display_frame(buf, None)
    log("Done.")

def main():
    btn = Button(PIN_BUTTON)
    log("AirBuddy: booted. Press button to run.")

    while True:
        try:
            btn.wait_for_press()
        except KeyboardInterrupt:
            # lets you break out cleanly when connected
            log("KeyboardInterrupt: returning to REPL")
            return

        run_display_demo()
        log("Cooldown (protect e-ink)...")
        time.sleep(5)

main()
