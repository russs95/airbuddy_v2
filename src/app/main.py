# src/app/main.py — AirBuddy 2.1 core loop (Pico / MicroPython)

import machine
import time
from machine import Pin, I2C

from src.app.boot_guard import enforce_debug_guard
from src.app.gps_init import init_gps


# ============================================================
# 0) CONSTANTS
# ============================================================
BTN_PIN = 15

GPS_UART_ID = 1
GPS_BAUD = 9600
GPS_TX_PIN = 8
GPS_RX_PIN = 9

DEBUG_FLAG_FILE = "debug_mode"


def init_i2c_bus():
    return I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)


def run(
        rtc_synced=None,
        wifi_boot=None,
        api_boot=None,               # ✅ new
        oled=None,
        air_sensor=None,
        boot_warmup_started=False,
        rtc_info=None
):
    # --- debug guard ---
    enforce_debug_guard(btn_pin=BTN_PIN, debug_flag_file=DEBUG_FLAG_FILE)

    # --- local imports to reduce boot RAM ---
    from config import load_config
    from src.input.button import AirBuddyButton
    from src.ui.oled import OLED
    from src.ui.spinner import Spinner
    from src.ui.waiting import WaitingScreen

    from src.ui.screens.co2 import CO2Screen
    from src.ui.screens.tvoc import TVOCScreen
    from src.ui.screens.temp import TempScreen
    from src.ui.screens.time import TimeScreen
    from src.ui.screens.summary import SummaryScreen

    from src.ui.screens.gps import GPSScreen
    from src.ui.screens.wifi import WiFiScreen
    from src.ui.screens.online import OnlineScreen
    from src.ui.screens.selfdestruct import SelfDestructScreen

    try:
        from src.ui.screens.logging import LoggingScreen
    except Exception:
        LoggingScreen = None

    from src.sensors.air import AirSensor
    from src.app.sysinfo import get_time_str, get_date_str
    from src.net.wifi_manager import WiFiManager
    from src.app.telemetry_state import TelemetryState

    # ============================================================
    # 3) HARDWARE + UI INIT
    # ============================================================
    if oled is None:
        oled = OLED()

    i2c = init_i2c_bus()

    # ✅ Use rtc_info passed from root boot. Do NOT touch DS3231 again.
    if isinstance(rtc_info, dict):
        rtc = rtc_info
    else:
        # fallback if someone runs src/app/main.py directly
        from src.app.rtc_sync import sync_system_rtc_from_ds3231
        rtc = sync_system_rtc_from_ds3231(i2c)

    gps = init_gps(
        uart_id=GPS_UART_ID,
        baud=GPS_BAUD,
        tx_pin=GPS_TX_PIN,
        rx_pin=GPS_RX_PIN
    )

    btn = AirBuddyButton(
        gpio_pin=BTN_PIN,
        click_window_s=1.4,
        debounce_ms=50,
        debug_hold_ms=2000
    )

    spinner = Spinner(oled)
    waiting = WaitingScreen()

    co2_screen = CO2Screen(oled)
    tvoc_screen = TVOCScreen(oled)
    temp_screen = TempScreen(oled)
    time_screen = TimeScreen(oled)
    summary_screen = SummaryScreen(oled)

    gps_screen = GPSScreen(oled)
    wifi_screen = WiFiScreen(oled)
    online_screen = OnlineScreen(oled)
    selfdestruct_screen = SelfDestructScreen(oled)
    logging_screen = LoggingScreen(oled) if LoggingScreen else None

    air = air_sensor if air_sensor is not None else AirSensor()
    wifi = WiFiManager()

    telemetry = TelemetryState(
        air_sensor=air,
        rtc_info_getter=lambda: rtc,
        wifi_manager=wifi
    )

    # ============================================================
    # STATUS STATE (seed from boot, update during runtime)
    # ============================================================
    status = {
        "wifi_ok": False,
        "gps_on": False,
        "api_ok": False,
    }

    if isinstance(wifi_boot, dict):
        status["wifi_ok"] = bool(wifi_boot.get("ok", False))

    if isinstance(api_boot, dict):
        status["api_ok"] = bool(api_boot.get("ok", False))

    # Show device assignment splash once at startup (4 seconds)
    def _show_assignment_splash(api_info):
        """
        Displays:
          device name
          home / room / community
        for ~4 seconds, then returns.
        """
        if not isinstance(api_info, dict):
            return
        if not api_info.get("ok"):
            return

        device_name = (api_info.get("device_name") or "").strip() or "AirBuddy"
        home_name = (api_info.get("home_name") or "").strip()
        room_name = (api_info.get("room_name") or "").strip()
        com_name = (api_info.get("community_name") or "").strip()

        fb = getattr(oled, "oled", None)
        if fb is None:
            return

        f_title = getattr(oled, "f_arvo16", None) or getattr(oled, "f_med", None)
        f_line = getattr(oled, "f_med", None) or getattr(oled, "f_small", None)

        fb.fill(0)

        # Title-ish: device name (centered)
        try:
            oled.draw_centered(f_title, device_name[:18], 6)
        except Exception:
            f_title.write(device_name[:18], 0, 6)

        y = 26

        # Home / room / community (left aligned for clarity)
        if home_name:
            f_line.write(("Home: " + home_name)[:21], 0, y); y += 12
        if room_name:
            f_line.write(("Room: " + room_name)[:21], 0, y); y += 12
        if com_name:
            f_line.write(("Com: " + com_name)[:21], 0, y); y += 12

        fb.show()

        # Hold ~4s, but don't trap the user if they click.
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 4000:
            try:
                a = btn.poll_action()
                if a:
                    break
            except Exception:
                pass
            time.sleep_ms(25)

    # ============================================================
    # CONFIG APPLY
    # ============================================================
    def refresh_cfg_apply():
        cfg = load_config()

        # GPS enable/disable immediately + maintain gps_on state
        status["gps_on"] = bool(cfg.get("gps_enabled", False)) and (gps is not None)

        if gps:
            try:
                if cfg.get("gps_enabled"):
                    gps.enable()
                else:
                    gps.disable()
            except Exception:
                pass

        return cfg

    cfg = refresh_cfg_apply()

    # If boot already started warmup, don't redo it here.
    if not boot_warmup_started:
        warmup_s = 4.0
        air.begin_sampling(warmup_seconds=warmup_s, source="boot")
        from src.ui.booter import Booter
        Booter(oled).show(duration=warmup_s, fps=18)

    # ✅ Show assignment splash once, right after boot work is done
    _show_assignment_splash(api_boot)

    # ============================================================
    # IDLE LOOP
    # ============================================================
    while True:
        cfg = refresh_cfg_apply()

        waiting.show(
            oled,
            line="Know your air",
            animate=False,
            wifi_ok=status["wifi_ok"],
            gps_on=status["gps_on"],
            api_ok=status["api_ok"],
        )
        btn.reset()

        while True:
            telemetry.tick(cfg, rtc_dict=rtc)

            action = btn.poll_action()
            if action is None:
                time.sleep_ms(25)
                continue

            if action == "debug":
                waiting.show(
                    oled,
                    line="Debug mode",
                    animate=False,
                    wifi_ok=status["wifi_ok"],
                    gps_on=status["gps_on"],
                    api_ok=status["api_ok"],
                )
                try:
                    with open(DEBUG_FLAG_FILE, "w") as f:
                        f.write("1")
                except Exception as e:
                    print("DEBUG:flag write failed:", repr(e))
                machine.reset()

            if action == "quad":
                selfdestruct_screen.show(btn=btn)
                waiting.show(
                    oled,
                    line="Know your air",
                    animate=False,
                    wifi_ok=status["wifi_ok"],
                    gps_on=status["gps_on"],
                    api_ok=status["api_ok"],
                )
                btn.reset()
                continue

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

                waiting.show(
                    oled,
                    line="Know your air",
                    animate=False,
                    wifi_ok=status["wifi_ok"],
                    gps_on=status["gps_on"],
                    api_ok=status["api_ok"],
                )
                btn.reset()
                continue

            if action == "triple":
                waiting.show(
                    oled,
                    line="Settings",
                    animate=False,
                    wifi_ok=status["wifi_ok"],
                    gps_on=status["gps_on"],
                    api_ok=status["api_ok"],
                )

                current = "gps"
                btn.reset()

                while True:
                    cfg = refresh_cfg_apply()

                    if current == "gps":
                        if not gps:
                            waiting.show(
                                oled,
                                line="GPS missing",
                                animate=False,
                                wifi_ok=status["wifi_ok"],
                                gps_on=status["gps_on"],
                                api_ok=status["api_ok"],
                            )
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
                            if logging_screen:
                                current = "logging"
                                continue
                            break
                        break

                    if current == "logging":
                        if not logging_screen:
                            break

                        res = logging_screen.show_live(
                            btn=btn,
                            get_queue_size=telemetry.get_queue_size,
                            get_last_sent=telemetry.get_last_sent,
                        )
                        if res == "next":
                            break
                        break

                waiting.show(
                    oled,
                    line="Know your air",
                    animate=False,
                    wifi_ok=status["wifi_ok"],
                    gps_on=status["gps_on"],
                    api_ok=status["api_ok"],
                )
                btn.reset()
                continue

            if action != "single":
                continue

            break

        # reading flow
        try:
            spinner.spin(duration=3.0)
            reading = air.finish_sampling(log=False)
        except Exception as e:
            print("[MAIN]sampling failed:", repr(e))
            last = air.get_last_logged()
            if last is None:
                waiting.show(
                    oled,
                    line="Sensor error",
                    animate=False,
                    wifi_ok=status["wifi_ok"],
                    gps_on=status["gps_on"],
                    api_ok=status["api_ok"],
                )
                time.sleep(3)
                continue
            reading = last

        co2_screen.show(reading)
        while btn.pin.value() == 1:
            time.sleep_ms(10)

        tvoc_screen.show(reading)
        while btn.pin.value() == 1:
            time.sleep_ms(10)

        temp_screen.show(reading, rtc_temp_c=rtc.get("temp_c"))
        while btn.pin.value() == 1:
            time.sleep_ms(10)

        def _get_latest():
            r = air.read_quick(source="summary")
            return r or reading

        summary_screen.show_live(
            get_reading=_get_latest,
            btn=btn,
            refresh_ms=3000,
            max_seconds=0
        )


if __name__ == "__main__":
    run()
