from machine import Pin, SPI
import utime
import sys

# -----------------------------------------
# AirBuddy v2 - E-Ink text smoke test
# Uses: /lib/epd2in13.py and your fonts folder
# Prints: "HELLO ROBBIE!" in the largest font that fits
# -----------------------------------------

TEXT = "HELLO ROBBIE!"

# ESP32 wiring (your current setup)
PIN_CS = 5
PIN_DC = 2
PIN_RST = 15
PIN_BUSY = 4
PIN_SCK = 18
PIN_MOSI = 23

SPI_ID = 2
SPI_BAUD = 4_000_000  # safe starting point for many e-ink boards


def _ensure_font_import_paths():
    """
    Make imports work whether you installed fonts as:
      - /fonts/*.py  (package folder at root)
      - /lib/fonts/*.py
    """
    # MicroPython usually includes '' and '/lib' already, but let's be explicit and robust.
    for p in ("", "/", "/lib", "/fonts", "/lib/fonts"):
        if p not in sys.path:
            sys.path.append(p)


def _load_font(modname):
    """
    Tries importing a font module from fonts.<modname> or directly <modname>.
    Returns a 'font object' with width/height/data.
    """
    # Most common: fonts/font12.py etc, with __init__.py in fonts folder.
    try:
        m = __import__("fonts." + modname, None, None, [modname])
        return m
    except Exception:
        pass

    # Fallback: if the module is directly importable
    try:
        m = __import__(modname)
        return m
    except Exception:
        return None


def _wrap_text_to_width(text, font, max_width):
    """
    Greedy word-wrap based on font.width.
    Returns list[str] lines that fit max_width.
    """
    words = text.split(" ")
    lines = []
    current = ""

    def w(s):
        return len(s) * font.width

    for word in words:
        if current == "":
            trial = word
        else:
            trial = current + " " + word

        if w(trial) <= max_width:
            current = trial
        else:
            # push current line
            if current:
                lines.append(current)
            current = word

            # if a single word is too wide, hard-break it
            if w(current) > max_width:
                chunk = ""
                for ch in current:
                    if w(chunk + ch) <= max_width:
                        chunk += ch
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                current = chunk

    if current:
        lines.append(current)

    return lines


def _choose_largest_font_that_fits(epd, text):
    """
    Try fonts from largest -> smallest, return (font_module, lines).
    """
    candidates = [
        "font24",
        "font20",
        "font16",
        "monaco16bold",
        "monaco16",
        "font12",
        "monaco12",
        "font8",
        "tiny",
    ]

    for name in candidates:
        font = _load_font(name)
        if not font or not hasattr(font, "width") or not hasattr(font, "height") or not hasattr(font, "data"):
            continue

        lines = _wrap_text_to_width(text, font, epd.width)

        total_h = len(lines) * font.height
        if total_h <= epd.height:
            # Also make sure each line fits (wrap function should guarantee, but double-check)
            ok = True
            for ln in lines:
                if len(ln) * font.width > epd.width:
                    ok = False
                    break
            if ok:
                return font, lines

    return None, None


def _draw_centered_lines(epd, buf, lines, font, colored=1):
    """
    Centers wrapped lines both horizontally and vertically.
    """
    total_h = len(lines) * font.height
    y = max(0, (epd.height - total_h) // 2)

    for ln in lines:
        x = max(0, (epd.width - (len(ln) * font.width)) // 2)
        epd.display_string_at(buf, x, y, ln, font, colored)
        y += font.height


def main():
    print("AirBuddy: main.py starting (text test)")

    _ensure_font_import_paths()

    # Import your EPD driver from /lib
    try:
        from epd2in13 import EPD
    except Exception as e:
        print("ERROR: could not import epd2in13 from /lib:", e)
        return

    spi = SPI(
        SPI_ID,
        baudrate=SPI_BAUD,
        polarity=0,
        phase=0,
        sck=Pin(PIN_SCK),
        mosi=Pin(PIN_MOSI),
    )

    epd = EPD(
        spi=spi,
        cs=Pin(PIN_CS),
        dc=Pin(PIN_DC),
        rst=Pin(PIN_RST),
        busy=Pin(PIN_BUSY),
    )

    print("Initializing EPD...")
    epd.init()
    print("Init OK")

    # Framebuffer (black)
    buf = bytearray(epd.width * epd.height // 8)
    epd.clear_frame(buf)

    font, lines = _choose_largest_font_that_fits(epd, TEXT)
    if not font:
        print("ERROR: no usable font found. Check that fonts are on-device with __init__.py")
        return

    print("Using font:", getattr(font, "__name__", "unknown"), "size:", font.width, "x", font.height)
    print("Lines:", lines)

    _draw_centered_lines(epd, buf, lines, font, colored=1)

    print("Refreshing display...")
    epd.display_frame(buf)
    print("Display refresh done")


# Run on boot
main()
