# epd2in13.py — patched for 212x104 (width not divisible by 8)
# Key fixes:
#  - Use correct row stride: row_bytes = (212 + 7)//8 = 27
#  - Send full buffer_size (row_bytes * height) bytes to panel RAM
#  - Fix pixel indexing to use row stride (not (x + y*width)//8)
#
# Panel: 2.13" 212(H) x 104(V)

import utime
import ustruct
from machine import Pin

EPD_WIDTH = 212
EPD_HEIGHT = 104

# Commands
PANEL_SETTING = 0x00
POWER_SETTING = 0x01
POWER_OFF = 0x02
POWER_ON = 0x04
BOOSTER_SOFT_START = 0x06

DATA_START_TRANSMISSION_1 = 0x10
DISPLAY_REFRESH = 0x12
DATA_START_TRANSMISSION_2 = 0x13

PLL_CONTROL = 0x30
VCOM_AND_DATA_INTERVAL_SETTING = 0x50
TCON_RESOLUTION = 0x61
VCM_DC_SETTING_REGISTER = 0x82
DEEP_SLEEP = 0x07

COLORED = 1
UNCOLORED = 0

ROTATE_0 = 0
ROTATE_90 = 1
ROTATE_180 = 2
ROTATE_270 = 3


class EPD:
    def __init__(self, spi, cs, dc, rst, busy):
        self.rst = rst
        self.rst.init(Pin.OUT, value=0)

        self.dc = dc
        self.dc.init(Pin.OUT, value=0)

        self.busy = busy
        # BUSY line: controller drives LOW while busy, HIGH when idle
        # Use pull-up if your panel/wiring needs it.
        self.busy.init(Pin.IN, Pin.PULL_UP)

        self.cs = cs
        self.cs.init(Pin.OUT, value=1)

        self.spi = spi

        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT
        self.rotate = ROTATE_0

        # --- FIX: row stride and buffer sizing for 212px wide panel ---
        self.row_bytes = (EPD_WIDTH + 7) // 8   # 27 bytes per row
        self.buffer_size = self.row_bytes * EPD_HEIGHT  # 2808 bytes total

    def init(self):
        self.reset()

        self.send_command(BOOSTER_SOFT_START, b"\x17\x17\x17")
        self.send_command(POWER_SETTING, b"\x03\x00\x2b\x2b\x09")

        self.send_command(POWER_ON)
        self.wait_until_idle()

        self.send_command(PANEL_SETTING, b"\xAF")
        self.send_command(PLL_CONTROL, b"\x3A")

        # Correct resolution bytes for 212 x 104
        self.send_command(TCON_RESOLUTION, ustruct.pack(">BH", EPD_WIDTH, EPD_HEIGHT))

        self.send_command(VCM_DC_SETTING_REGISTER, b"\x12")
        self.send_command(VCOM_AND_DATA_INTERVAL_SETTING, b"\x87")

        return 0

    def delay_ms(self, delaytime):
        utime.sleep_ms(delaytime)

    def send_command(self, command, data=None):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([command]))
        self.cs(1)
        if data is not None:
            self.send_data(data)

    def send_data(self, data):
        self.dc(1)
        self.cs(0)
        if isinstance(data, (bytes, bytearray)):
            self.spi.write(bytearray(data))
        else:
            self.spi.write(bytearray([data]))
        self.cs(1)

    def wait_until_idle(self, timeout_ms=10000):
        # BUSY LOW = busy, HIGH = idle
        start = utime.ticks_ms()
        while self.busy.value() == 0:
            if utime.ticks_diff(utime.ticks_ms(), start) > timeout_ms:
                print("BUSY timeout, continuing")
                break
            self.delay_ms(50)

    def reset(self):
        self.rst(0)
        self.delay_ms(200)
        self.rst(1)
        self.delay_ms(200)

    def display_frame(self, frame_buffer_black, frame_buffer_red=None):
        # --- FIX: send full buffer_size bytes, not (width*height//8) ---
        if frame_buffer_black is not None:
            self.send_command(DATA_START_TRANSMISSION_1)
            self.delay_ms(2)
            for i in range(self.buffer_size):
                self.send_data(frame_buffer_black[i])
            self.delay_ms(2)

        if frame_buffer_red is not None:
            self.send_command(DATA_START_TRANSMISSION_2)
            self.delay_ms(2)
            for i in range(self.buffer_size):
                self.send_data(frame_buffer_red[i])
            self.delay_ms(2)

        self.send_command(DISPLAY_REFRESH)
        self.wait_until_idle()

    def sleep(self):
        self.send_command(POWER_OFF)
        self.wait_until_idle()
        self.send_command(DEEP_SLEEP, b"\xA5")

    def set_rotate(self, rotate):
        # Rotation changes logical width/height for drawing bounds,
        # but the underlying buffer still targets the panel's native mapping.
        if rotate == ROTATE_0:
            self.rotate = ROTATE_0
            self.width = EPD_WIDTH
            self.height = EPD_HEIGHT
        elif rotate == ROTATE_90:
            self.rotate = ROTATE_90
            self.width = EPD_HEIGHT
            self.height = EPD_WIDTH
        elif rotate == ROTATE_180:
            self.rotate = ROTATE_180
            self.width = EPD_WIDTH
            self.height = EPD_HEIGHT
        elif rotate == ROTATE_270:
            self.rotate = ROTATE_270
            self.width = EPD_HEIGHT
            self.height = EPD_WIDTH

    def set_pixel(self, frame_buffer, x, y, colored):
        if (x < 0 or x >= self.width or y < 0 or y >= self.height):
            return

        if self.rotate == ROTATE_0:
            self.set_absolute_pixel(frame_buffer, x, y, colored)
        elif self.rotate == ROTATE_90:
            point_temp = x
            x = EPD_WIDTH - y - 1
            y = point_temp
            self.set_absolute_pixel(frame_buffer, x, y, colored)
        elif self.rotate == ROTATE_180:
            x = EPD_WIDTH - x - 1
            y = EPD_HEIGHT - y - 1
            self.set_absolute_pixel(frame_buffer, x, y, colored)
        elif self.rotate == ROTATE_270:
            point_temp = x
            x = y
            y = EPD_HEIGHT - point_temp - 1
            self.set_absolute_pixel(frame_buffer, x, y, colored)

    def set_absolute_pixel(self, frame_buffer, x, y, colored):
        if x < 0 or x >= EPD_WIDTH or y < 0 or y >= EPD_HEIGHT:
            return

        # --- FIX: stride-aware indexing ---
        idx = y * self.row_bytes + (x >> 3)
        mask = 0x80 >> (x & 7)

        # 0 bit = colored pixel, 1 bit = white
        if colored:
            frame_buffer[idx] &= ~mask
        else:
            frame_buffer[idx] |= mask

    def draw_char_at(self, frame_buffer, x, y, char, font, colored):
        char_offset = (ord(char) - ord(" ")) * font.height * (
            (int(font.width / 8) + (1 if font.width % 8 else 0))
        )
        offset = 0

        for j in range(font.height):
            for i in range(font.width):
                if font.data[char_offset + offset] & (0x80 >> (i % 8)):
                    self.set_pixel(frame_buffer, x + i, y + j, colored)
                if i % 8 == 7:
                    offset += 1
            if font.width % 8 != 0:
                offset += 1

    def display_string_at(self, frame_buffer, x, y, text, font, colored):
        refcolumn = x
        for ch in text:
            self.draw_char_at(frame_buffer, refcolumn, y, ch, font, colored)
            refcolumn += font.width
