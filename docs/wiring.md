# Wiring

| EINK Pin (Pi Header) | Signal         | Wire Color | ESP32 Pin |
| -------------------: | -------------- | ---------- | --------- |
|                **1** | **3V3**        | ⚪ White    | 3V3       |
|                **6** | **GND**        | ⚫ Grey     | GND       |
|               **19** | **DIN / MOSI** | 🟤 Blue    | D23       |
|               **23** | **SCK / CLK**  | 🟡 Yellow  | D18       |
|               **24** | **BUSY**       | ⚪ White    | D4        |
|               **26** | **CS**         | 🟤 Brown   | D5        |
|               **22** | **DC**         | 🟠 Orange  | D2        |
|               **11** | **RST**        | 🟣 Purple  | D15       |


⚠️ BUSY WARNING
The BUSY signal is an OUTPUT from the e-ink display.
If BUSY is wired to the wrong Pi header pin, it will read constant LOW
and the display will never complete a refresh (random pixel noise).

BUSY is located on Pi header pin 24 (GPIO8).
It is NOT on pin 9 or pin 16.

⚠️ White 4-pin connector note
The white JST connector on the Waveshare board provides ONLY:
VCC, GND, DIN (MOSI), SCK (CLK).
It does NOT provide CS, DC, RST, or BUSY.
Those must be wired from the 40-pin header.

