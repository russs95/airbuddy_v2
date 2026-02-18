# src/app/main.py — AirBuddy 2.1 core loop (STABLE INPUT VERSION)

import machine
import time
from machine import Pin, I2C

from src.app.boot_guard import enforce_debug_guard
from src.app.gps_init import init_gps


# ============================================================
# CONSTANTS
# ============================================================
BTN_PIN = 15

GPS_UART_ID = 1
GPS_BAUD = 9600
GPS_TX_PIN = 8
GPS_RX_PIN = 9

DEBUG_FLAG_FILE = "debug_mode"

TELEMETRY_START_DELAY_MS = 15000
CFG_REFRESH_MS = 8000

WAIT_POLL_MS = 25


# ============================================================
# GC helper
# ============================================================
def _gc():
    try:
        import gc
        gc.collect()
    except Exception:
        pass


def init_i2c_bus():
    return I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)


# ============================================================
# RUN
# ============================================================
def run(
        rtc_synced=None,
        wifi_boot=None,
        api_boot=None,
        oled=None,
        air_sensor=None,
        boot_warmup_started=False,
        rtc_info=None
):

    enforce_debug_guard(btn_pin=BTN_PIN, debug_flag_file=DEBUG_FLAG_FILE)

    from config import load_config
    from src.input.button import AirBuddyButton
    from src.ui.waiting import WaitingScreen
    from src.sensors.air import AirSensor
    from src.net.wifi_manager import WiFiManager

    if oled is None:
        from src.ui.oled import OLED
        oled = OLED()

    i2c = init_i2c_bus()

    if isinstance(rtc_info, dict):
        rtc = rtc_info
    else:
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

    waiting = WaitingScreen()
    air = air_sensor if air_sensor else AirSensor()
    wifi = WiFiManager()

    # --------------------------------------------------------
    # STATUS FLAGS
    # --------------------------------------------------------
    status = {
        "wifi_ok": bool(isinstance(wifi_boot, dict) and wifi_boot.get("ok")),
        "gps_on": bool(gps),
        "api_ok": bool(isinstance(api_boot, dict) and api_boot.get("ok")),
    }

    # --------------------------------------------------------
    # CONFIG CACHE
    # --------------------------------------------------------
    _cfg = {}
    _next_cfg_refresh = 0

    def _refresh_cfg(force=False):
        nonlocal _cfg, _next_cfg_refresh
        now = time.ticks_ms()

        if (not force) and time.ticks_diff(now, _next_cfg_refresh) < 0:
            return _cfg

        try:
            c = load_config()
            if isinstance(c, dict):
                _cfg = c
        except Exception:
            pass

        _next_cfg_refresh = time.ticks_add(now, CFG_REFRESH_MS)
        return _cfg

    cfg = _refresh_cfg(force=True)

    # --------------------------------------------------------
    # TELEMETRY (deferred)
    # --------------------------------------------------------
    telemetry = None
    telemetry_started = False
    telemetry_ready_at = time.ticks_add(time.ticks_ms(), TELEMETRY_START_DELAY_MS)

    def _start_telemetry_if_ready():
        nonlocal telemetry, telemetry_started

        if telemetry_started:
            return

        if not bool(cfg.get("telemetry_enabled", True)):
            telemetry_started = True
            return

        if time.ticks_diff(time.ticks_ms(), telemetry_ready_at) < 0:
            return

        try:
            from src.app.telemetry_state import TelemetryState
            telemetry = TelemetryState(
                air_sensor=air,
                rtc_info_getter=lambda: rtc,
                wifi_manager=wifi
            )
        except Exception:
            telemetry = None

        telemetry_started = True
        _gc()

    # --------------------------------------------------------
    # LAZY SCREEN LOADER
    # --------------------------------------------------------
    screens = {}

    def get_screen(name):
        if name in screens:
            return screens[name]

        try:
            if name == "co2":
                from src.ui.screens.co2 import CO2Screen
                screens[name] = CO2Screen(oled)
            elif name == "tvoc":
                from src.ui.screens.tvoc import TVOCScreen
                screens[name] = TVOCScreen(oled)
            elif name == "temp":
                from src.ui.screens.temp import TempScreen
                screens[name] = TempScreen(oled)
            elif name == "summary":
                from src.ui.screens.summary import SummaryScreen
                screens[name] = SummaryScreen(oled)
            elif name == "time":
                from src.ui.screens.time import TimeScreen
                screens[name] = TimeScreen(oled)
            elif name == "gps":
                from src.ui.screens.gps import GPSScreen
                screens[name] = GPSScreen(oled)
            elif name == "wifi":
                from src.ui.screens.wifi import WiFiScreen
                screens[name] = WiFiScreen(oled)
            elif name == "online":
                from src.ui.screens.online import OnlineScreen
                screens[name] = OnlineScreen(oled)
            elif name == "logging":
                from src.ui.screens.logging import LoggingScreen
                screens[name] = LoggingScreen(oled)
        except Exception:
            screens[name] = None
            _gc()

        return screens.get(name)

    # ============================================================
    # MAIN LOOP
    # ============================================================
    while True:

        cfg = _refresh_cfg(force=False)
        _start_telemetry_if_ready()

        # --------------------------------------------------------
        # WAITING SCREEN (uses show_live — handles flush + heartbeat)
        # --------------------------------------------------------
        action = waiting.show_live(
            oled,
            btn,
            line="Know your air...",
            animate=False,
            wifi_ok=status["wifi_ok"],
            gps_on=status["gps_on"],
            api_ok=status["api_ok"],
            poll_ms=WAIT_POLL_MS
        )

        # --------------------------------------------------------
        # HANDLE ACTION
        # --------------------------------------------------------
        if action == "quad":
            machine.reset()

        if action == "triple":
            # You can reinsert your settings carousel here
            continue

        if action == "double":
            ts = get_screen("time")
            if ts:
                from src.app.sysinfo import get_time_str, get_date_str

                ts.show_live(
                    get_date_str=get_date_str,
                    get_time_str=get_time_str,
                    get_source=lambda: "RTC",
                    get_temp_c=lambda: rtc.get("temp_c"),
                    btn=btn
                )
            continue

        # --------------------------------------------------------
        # SINGLE CLICK → SENSOR FLOW
        # --------------------------------------------------------
        if action == "single":
            try:
                reading = air.finish_sampling(log=False)
            except Exception:
                continue

            _gc()

            for name in ("co2", "tvoc", "temp"):
                scr = get_screen(name)
                if scr:
                    scr.show(reading)
                    while btn.pin.value() == 1:
                        time.sleep_ms(10)

            summ = get_screen("summary")
            if summ:
                summ.show_live(get_reading=lambda: reading, btn=btn)

            _gc()
