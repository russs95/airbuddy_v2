# 🌬️ airBuddy  
**Open‑source air quality testing for one's home and community**

---

## 🌍 1. Overview

**airBuddy** is a small, open‑source air quality testing device.  Version 2.1 is built on a **Raspberry Pi Zero 2 W**.  
The airBuddy let's one test and track the air quality in one's home-- and later one's community.   The project uses super inexpensive and sensor components that are available just about anywhere, so that just about anyone can put it togeter.

With one press of a button, airBuddy:
- Measures **temperature & humidity**
- Reads **eCO₂ (equivalent CO₂)** and **TVOC (total volatile organic compounds)**
- Estimates overall **air quality**
- Displays the results on a compact OLED screen
- Logs readings to a local data file for long‑term tracking

The goal is simple:

> **If people can measure their air, they can demand better air.**

airBuddy is designed to be:
- Affordable
- Hackable
- Community‑deployable
- Fully open source

---

## 2. Hardware Components

| Component | Description |
|--------|-------------|
| 🧠 **Raspberry Pico 2 W** | Core computer - Make sure you buy the version with the pin hat preinstalled! |
 🔌 **Micro USB cable(s)** | The Pico has one micro usb port.  You'll need a cable to connect to your computer to load and develop airBuddy code |
| 🌫 **ENS160 + AHT21 Sensor Board** | Measures eCO₂, TVOC, temperature & humidity - make sure the pin head is preinstalled! |
| 🖥 **0.96" SSD1306 OLED (I²C)** | 128×64 pixel display - or bring your own and customize the code!|
| 🔘 **Momentary Push Button** | A solid metal momentary push button - Triggers an air quality test |
| 🔌 **Jumper Wires** | Get a code assortment of colors.  If your pin heads are pre-installed all you need is female-to-female cables |
| 🔋 **5V Power Source** | Other than your computer you'll need a way to charge.  You can use a USB power bank or a direct pin connection to the Pico with a battery shield |

| Component                                             | Description                                                                                                                                  |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| 🧠 **Raspberry Pi Pico 2 W**                          | Core microcontroller with Wi-Fi. Make sure you buy the version with **pre-soldered pin headers**.                                            |
| 🔌 **Micro USB cable(s)**                             | Used to power the Pico and upload MicroPython / airBuddy firmware during development.                                                        |
| 🌫 **ENS160 + AHT21 Sensor Board**                    | Primary air sensor measuring **eCO₂, TVOC, temperature, and humidity**. Choose a version with **preinstalled pin headers**.                  |
| 🖥 **0.96" SSD1306 OLED (I²C)**                       | 128×64 pixel display for UI and readings. (Optional second OLED later if desired.)                                                           |
| 🔘 **Momentary Push Button**                          | Solid metal momentary button used to trigger readings, wake screens, or cycle views.                                                         |
| 🔌 **Jumper Wires**                                   | Female-to-female jumper wires (color assortment recommended).                                                                                |
| 🔋 **5V Power Source**                                | USB power bank, wall adapter, or battery shield (Li-ion / 18650 / solar later).                                                              |
| 🧭 **NEO-6M GPS Module**                              | Provides **latitude, longitude, altitude, and UTC time** for geotagged air readings. UART-based.                                             |
| 🧩 **TCA9548A I²C Multiplexer**                       | Expands the Pico’s I²C bus to **8 independent channels**, allowing multiple OLEDs, sensors, and future expansions without address conflicts. |
| ⏰ **DS3231 RTC Module**                               | High-accuracy real-time clock with coin-cell backup. Keeps time when the device is powered off.                                              |
| 🌬 **(Optional) Particle Sensor (PMS7003 / PMS5003)** | Measures **PM1.0 / PM2.5 / PM10** particulate matter via UART. Adds real air pollution insight.                                              |
| 🧪 **(Optional) True CO₂ Sensor (SCD30 / SCD41)**     | NDIR-based **true CO₂ ppm** measurement. More accurate than eCO₂ estimates from VOC sensors.                                                 |




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
