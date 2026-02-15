#src/app/main.py—AirBuddy2.1coreloop(Pico/MicroPython)

import machine
from machine import Pin, I2C
from src.app.boot_guard import enforce_debug_guard
from src.app.rtc_sync import sync_system_rtc_from_ds3231
from src.app.gps_init import init_gps

BTN_PIN = 15

GPS_UART_ID = 1
GPS_BAUD = 9600
GPS_TX_PIN = 8
GPS_RX_PIN = 9

DEBUG_FLAG_FILE = "debug_mode"


def init_i2c_bus():
    return I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)


def run(rtc_synced=None, wifi_boot=None):
    enforce_debug_guard(btn_pin=BTN_PIN, debug_flag_file=DEBUG_FLAG_FILE)

    from src.input.button import AirBuddyButton
    from src.ui.oled import OLED
    from src.ui.booter import Booter
    from src.ui.spinner import Spinner
    from src.ui.waiting import WaitingScreen
    from src.ui.screens.co2 import CO2Screen
    from src.ui.screens.tvoc import TVOCScreen
    from src.ui.screens.temp import TempScreen
    from src.ui.screens.time import TimeScreen
    from src.ui.screens.summary import SummaryScreen
    from src.ui.screens.gps import GPSScreen
    from src.ui.screens.wifi import WiFiScreen
    from src.ui.screens.online import OnlineScreen  # 🔥 new
    from src.sensors.air import AirSensor
    from src.app.sysinfo import get_time_str, get_date_str
    from src.app.config import load_config

    oled = OLED()
    i2c = init_i2c_bus()

    rtc = sync_system_rtc_from_ds3231(i2c)
    print("RTC:", rtc)

    gps = init_gps(
        uart_id=GPS_UART_ID,
        baud=GPS_BAUD,
        tx_pin=GPS_TX_PIN,
        rx_pin=GPS_RX_PIN
    )

    cfg = load_config()

    # Apply GPS setting
    if gps:
        if cfg.get("gps_enabled"):
            try:
                gps.enable()
            except:
                pass
        else:
            try:
                gps.disable()
            except:
                pass

    btn = AirBuddyButton(gpio_pin=BTN_PIN)
    spinner = Spinner(oled)
    waiting = WaitingScreen()
    co2_screen = CO2Screen(oled)
    tvoc_screen = TVOCScreen(oled)
    temp_screen = TempScreen(oled)
    time_screen = TimeScreen(oled)
    summary_screen = SummaryScreen(oled)

    gps_screen = GPSScreen(oled)
    wifi_screen = WiFiScreen(oled)
    online_screen = OnlineScreen(oled)  # 🔥 ready for next step

    air = AirSensor()
    warmup_s = 4.0
    air.begin_sampling(warmup_seconds=warmup_s, source="boot")
    Booter(oled).show(duration=warmup_s, fps=18)

    while True:
        waiting.show(oled, line="Know your air", animate=False)
        action = btn.wait_for_action()

        # ----------------------------
        # Debug mode
        # ----------------------------
        if action == "debug":
            waiting.show(oled, line="Debug mode", animate=False)
            try:
                f = open(DEBUG_FLAG_FILE, "w")
                f.write("1")
                f.close()
            except Exception as e:
                print("DEBUG:flag write failed:", repr(e))
            machine.reset()

        # ----------------------------
        # Time screen
        # ----------------------------
        if action == "double":

            def _source():
                if rtc.get("synced") and (not rtc.get("osf")):
                    return "RTC"
                if rtc.get("synced"):
                    return "RTC?"
                return "SYS"

            def _temp():
                return rtc.get("temp_c")

            time_screen.show_live(
                get_date_str=get_date_str,
                get_time_str=get_time_str,
                get_source=_source,
                get_temp_c=_temp,
                btn=btn,
                max_seconds=0,
                blink_ms=500,
                refresh_every_blinks=2
            )
            continue

        # ----------------------------
        # Settings Flow
        # ----------------------------
        if action == "triple":
            waiting.show(oled, line="Settings", animate=False)

            current = "gps"

            while True:

                if current == "gps":
                    if not gps:
                        waiting.show(oled, line="GPS missing", animate=False)
                        import time
                        time.sleep(2)
                        break

                    res = gps_screen.show_live(gps=gps, btn=btn)

                    if res == "next":
                        current = "wifi"
                        continue
                    break

                if current == "wifi":
                    res = wifi_screen.show_live(btn=btn)

                    if res == "next":
                        current = "online"
                        continue
                    break

                if current == "online":
                    res = online_screen.show_live(btn=btn)

                    if res == "next":
                        break
                    break

            continue

        # ----------------------------
        # Future click placeholders
        # ----------------------------
        if action == "quad":
            waiting.show(oled, line="4-click TBD", animate=False)
            import time
            time.sleep(1)
            continue

        if action == "penta":
            waiting.show(oled, line="5-click TBD", animate=False)
            import time
            time.sleep(1)
            continue

        # ----------------------------
        # Main Air Reading Flow
        # ----------------------------
        if action != "single":
            continue

        try:
            spinner.spin(duration=3.0)
            reading = air.finish_sampling(log=False)
        except Exception as e:
            print("[MAIN]sampling failed:", repr(e))
            last = air.get_last_logged()
            if last is None:
                waiting.show(oled, line="Sensor error", animate=False)
                import time
                time.sleep(3)
                continue
            reading = last

        co2_screen.show(reading)
        while btn.pin.value() == 1:
            import time
            time.sleep_ms(10)

        tvoc_screen.show(reading)
        while btn.pin.value() == 1:
            import time
            time.sleep_ms(10)

        temp_screen.show(reading, rtc_temp_c=rtc.get("temp_c"))
        while btn.pin.value() == 1:
            import time
            time.sleep_ms(10)

        def _get_latest():
            return air.read_quick(source="summary") or reading

        summary_screen.show_live(
            get_reading=_get_latest,
            btn=btn,
            refresh_ms=3000,
            max_seconds=0
        )


if __name__ == "__main__":
    run()
