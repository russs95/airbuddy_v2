## Raspberry Pi Pico W — AirBuddy 2.1 Wiring

**Orientation:** USB UP  
**Right column order:** Top → bottom corresponds to physical pins **40 → 21**

| Left Side (Pins 1–20)                                      | Right Side (Pins 40–21)                                      |
|------------------------------------------------------------|--------------------------------------------------------------|
| 🟩 **1** GP0 → OLED (SDA), ENS160 (SDA), RTC (SDA)           | ⬜ **40** VBUS                                                |
| 🟨 **2** GP1 → OLED (SCL), ENS160 (SCL), RTC (SCL)           | ⬜ **39** 5V IN from BATTERY                                  |
| ⬜ **3** GND                                                 | ⬛ **38** GND from BATTERY                                    |
| ⬜ **4** GP2                                                 | ⬜ **37** 3V3_EN                                              |
| ⬜ **5** GP3                                                 | 🟥 **36** 3V3(OUT) → OLED VCC, ENS160 VCC, RTC VCC, GPS            |
| ⬜ **6** GP4                                                 | ⬜ **35** ADC_VREF                                            |
| ⬜ **7** GP5                                                 | ⬜ **34** GP28 ADC2                                           |
| ⬜ **8** GND                                                 | ⬛ **33** GND / AGND → OLED GND, ENS160 GND, RTC GND          |
| ⬜ **9** GP6                                                 | ⬜ **32** GP27 ADC1                                           |
| ⬜ **10** GP7                                                | ⬜ **31** GP26 ADC0                                           |
| 🔵 **11** GP8 → GPS RX                                       | ⬜ **30** RUN                                                 |
| 🟠 **12** GP9 → GPS TX                                       | ⬜ **29** GP22                                                |
| ⬛ **13** GND → GPS GROUND                                   | 🟪 **28** GND → BUTTON GND                                   |
| ⬜ **14** GP10                                               | ⬜ **27** GP21                                                |
| ⬜ **15** GP11                                               | ⬜ **26** GP20                                                |
| ⬜ **16** GP12                                               | ⬜ **25** GP19                                                |
| ⬜ **17** GP13                                               | ⬜ **24** GP18                                                |
| ⬛ **18** GND                                                 | ⬜ **23** GND                                                 |
| ⬜ **19** GP14                                               | ⬜ **22** GP17                                                |
| 🟪 **20** GP15 → BUTTON                                      | ⬜ **21** GP16                                                |


**Notes:**
- All I²C devices share **GP0 (SDA)** and **GP1 (SCL)**
- All peripherals are powered from **3V3(OUT)** (not VBUS)
- All GND pins are common
- Push button uses **internal pull-up** on GP15

