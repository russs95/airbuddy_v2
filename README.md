

# 🌬️ airBuddy  
**Open‑source air quality testing for community health & climate justice**

---

## 🌍 1. Overview

**airBuddy** is a small, open‑source air quality testing device.  
It empowers individuals, schools, neighborhoods, and communities to **measure the air they breathe** and take ownership of their environmental health through **knowledge, transparency, and data**.  The project uses super inexpensive and sensor components that are available just about anywhere, so that just about anyone can put it togeter.

Airbuddy2 is a MicroPython-based embedded project for compact air-quality monitoring.
Goal: keep a Pico-first layout that is ready to scale to ESP32 targets.
Goal: provide a minimal, clean structure for firmware, drivers, and UI modules.
Goal: document bring-up notes and wiring in a lightweight docs folder.

With one press of a button, airBuddy:
- Measures **temperature & humidity**
- Reads **eCO₂ (equivalent CO₂)** and **TVOC (total volatile organic compounds)**
- Estimates overall **air quality**
- Displays the results on a compact EINK screen
- Logs readings to a local data file for long‑term tracking

The goal is simple:

> **If people can measure their air, they can demand better air.**

airBuddy is designed to be:
- Affordable
- Hackable
- Community‑deployable
- Fully open source

---



## 🎨 eInk Reader
Board orientation: Buttons on Top

| Left Side (Pins 2–40) | Right Side (Pins 1–39) |
|:----------------------:|:----------------------:|
| □ **2**            | ⚪ **1** → ESP 3V3 |
| □ **4**            | □ **3**            |
| ⚪ **6** → GND     | □ **5**            |
| □ **8**            | □ **7**            |
| □ **10**           | □ **9**             |
| □ **12**           | 🟣 **11** → ESP D15 |
| □ **14**           | □ **13**            |
| □ **16**           | □ **15**            |
| ⚪ **18**→ ESP D4  | □ **17**            |
| □ **20**           | 🟤 **19** → ESP D23 |
| 🟠 **22** → ESP D2 | □ **21**            |
| □ **24**           | 🟡 **23** → ESP D18 |
| 🟤 **26** → ESP D5 | □ **25**            |
| □ **28**           | □ **27**            |
| □ **30**           | □ **29**            |
| □ **32**           | □ **31**            |
| □ **34**           | □ **33**            |
| □ **36**           | □ **35**            |
| □ **38**           | □ **37**            |
| □ **40**           | □ **39**            |

E-ink cable below 
---



## ESP32
Board orientation: USB UP

| Left Side (Pins 1-29) | Right Side (Pins 2–30) |
|:----------------------:|:----------------------:|
| □ **2**            | ⚪ **1** → ESP 3V3 |
| □ **4**            | □ **3**            |
| ⚪ **6** → GND     | □ **5**            |
| □ **8**            | □ **7**            |
| □ **10**           | □ **9**             |
| □ **12**           | 🟣 **11** → ESP D15 |
| □ **14**           | □ **13**            |
| □ **16**           | □ **15**            |
| ⚪ **18**→ ESP D4  | □ **17**            |
| □ **20**           | 🟤 **19** → ESP D23 |
| 🟠 **22** → ESP D2 | □ **21**            |
| □ **24**           | 🟡 **23** → ESP D18 |
| 🟤 **26** → ESP D5 | □ **25**            |
| □ **28**           | □ **27**            |
| □ **30**           | □ **29**            |
| □ **32**           | □ **31**            |
| □ **34**           | □ **33**            |
| □ **36**           | □ **35**            |
| □ **38**           | □ **37**            |
| □ **40**           | □ **39**            |

E-ink cable below 
---

## 🧩 2. Hardware Components

| Component | Description |
|--------|-------------|
| 🧠 **Raspberry Pi Pico or ESP32** | Core computer - Make sure you buy the version with the pin hat preinstalled! |
| 💾 **MicroSD Card (≥8GB)** | 8GB is more than enough to install Raspberry Pi OS 6 bit |
| 🔋 **5V Power Source** | USB power bank or a direct USB plug connection |
 🔌 **Micro USB cable(s)** | The Pi Zero has only two micro-usb ports. You'll need at least one to connect to your power source |
| 🌫 **ENS160 + AHT21 Sensor Board** | Measures eCO₂, TVOC, temperature & humidity - make sure the pin head is preinstalled! |
| 🖥 **0.96" SSD1306 OLED (I²C)** | 128×64 pixel display - or bring your own and customize the code!|
| 🔘 **Momentary Push Button** | A solid metal momentary push button - Triggers an air quality test |
| 🔌 **Jumper Wires** | Get a code assortment of colors.  If your pin heads are pre-installed all you need is female-to-female cables |


---

## 🌬️ 3. What airBuddy Does

When powered on, airBuddy shows an idle screen:

> **“airBuddy — Press Button”**

When the button is pressed:
1. An ASCII spinner appears while readings are gathered  
2. The sensors collect:
   - Temperature (°C)
   - Humidity (%)
   - eCO₂ (ppm equivalent)
   - TVOC (ppb)
3. A simple air‑quality rating is calculated
4. Results are displayed for **10 seconds**
5. The readings are logged to `/data/`
6. The device returns to idle mode

---

# 🌬️ airBuddy Wiring Guide  
### for Raspberry Pi Zero 2 W (SD Card Up, Power LED Down)

---

---

## 🎨 eInk Reader
Board orientation: Buttons on Top

| Left Side (Pins 2–40) | Right Side (Pins 1–39) |
|:----------------------:|:----------------------:|
| □ **2**            | ⚪ **1** → ESP 3V3 |
| □ **4**            | □ **3**            |
| ⚪ **6** → GND     | □ **5**            |
| □ **8**            | □ **7**            |
| □ **10**           | □ **9**             |
| □ **12**           | 🟣 **11** → ESP D15 |
| □ **14**           | □ **13**            |
| □ **16**           | □ **15**            |
| ⚪ **18**→ ESP D4  | □ **17**            |
| □ **20**           | 🟤 **19** → ESP D23 |
| 🟠 **22** → ESP D2 | □ **21**            |
| □ **24**           | 🟡 **23** → ESP D18 |
| 🟤 **26** → ESP D5 | □ **25**            |
| □ **28**           | □ **27**            |
| □ **30**           | □ **29**            |
| □ **32**           | □ **31**            |
| □ **34**           | □ **33**            |
| □ **36**           | □ **35**            |
| □ **38**           | □ **37**            |
| □ **40**           | □ **39**            |

E-ink cable below 
---

---

## 🌱 Why airBuddy Matters

Air pollution is one of the largest hidden public‑health crises on Earth.  
Yet most people cannot measure the air in their homes, schools, or neighborhoods.

airBuddy is about **democratizing environmental data**.

By making air quality measurable, visible, and shareable:
- Communities can identify problems
- Activists can collect evidence
- Families can protect their health
- Cities can be held accountable

**Clean air should not be a luxury.**

