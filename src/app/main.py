# src/app/main.py — AirBuddy 2.1 core loop (Revised)

import machine
import time

from src.app.boot_guard import enforce_debug_guard

try:
    from src.hal.board import init_i2c, gps_pins
except Exception:
    init_i2c = None
    gps_pins = None

from src.ui.clicks import (
    gc_collect as _gc,
    reset_and_flush as _reset_and_flush,
)

from src.ui.flows import (
    connectivity_carousel,
    sensor_carousel,
    time_flow,
    selfdestruct_flow,
)

ENABLE_DEBUG_HOLD_FLAG = False
DEBUG_FLAG_FILE = "debug_mode"


# ------------------------------------------------------------
# Resolve button pin safely
# ------------------------------------------------------------

def _resolve_btn_pin_default():
    try:
        import src.hal.board as b
        fn = getattr(b, "btn_pin", None)
        if callable(fn):
            return int(fn())
        if hasattr(b, "BTN_PIN"):
            return int(getattr(b, "BTN_PIN"))
    except Exception:
        pass
    return 15


# ============================================================
# MAIN RUN
# ============================================================

def run(
        rtc_synced=None,
        wifi_boot=None,
        api_boot=None,
        oled=None,
        air_sensor=None,
        boot_warmup_started=False,
        rtc_info=None,
):

    BTN_PIN = _resolve_btn_pin_default()
    enforce_debug_guard(btn_pin=BTN_PIN, debug_flag_file=DEBUG_FLAG_FILE)

    from config import load_config
    from src.input.button import AirBuddyButton
    from src.ui.waiting import WaitingScreen
    from src.net.wifi_manager import WiFiManager
    from src.app.gps_init import init_gps

    if oled is None:
        from src.ui.oled import OLED
        oled = OLED()

    # ------------------------------------------------------------
    # I2C (fixed freq)
    # ------------------------------------------------------------

    if init_i2c:
        i2c = init_i2c()
    else:
        from machine import I2C, Pin
        i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)

    rtc = rtc_info if isinstance(rtc_info, dict) else {}

    # ------------------------------------------------------------
    # GPS INIT
    # ------------------------------------------------------------

    if gps_pins:
        GPS_UART_ID, GPS_BAUD, GPS_TX_PIN, GPS_RX_PIN = gps_pins()
    else:
        GPS_UART_ID, GPS_BAUD, GPS_TX_PIN, GPS_RX_PIN = (1, 9600, 8, 9)

    try:
        gps = init_gps(
            uart_id=GPS_UART_ID,
            baud=GPS_BAUD,
            tx_pin=GPS_TX_PIN,
            rx_pin=GPS_RX_PIN,
        )
    except Exception:
        gps = None

    gps_detected = False

    def _probe_gps():
        nonlocal gps_detected
        if gps is None:
            gps_detected = False
            return
        try:
            if hasattr(gps, "any") and gps.any():
                data = gps.read(32) or b""
                if data:
                    gps_detected = True
        except Exception:
            pass

    # ------------------------------------------------------------
    # CORE OBJECTS
    # ------------------------------------------------------------

    btn = AirBuddyButton(
        gpio_pin=BTN_PIN,
        click_window_s=2.2,
        debounce_ms=45,
        debug_hold_ms=1500,
    )

    waiting = WaitingScreen()
    wifi = WiFiManager()
    air = air_sensor

    status = {
        "wifi_ok": bool(isinstance(wifi_boot, dict) and wifi_boot.get("ok")),
        "api_ok": False,      # Now dynamic from telemetry
        "gps_on": False,
    }

    # ------------------------------------------------------------
    # TELEMETRY
    # ------------------------------------------------------------

    telemetry = None
    telemetry_started = False

    def start_telemetry_if_ready(cfg):
        nonlocal telemetry, telemetry_started

        if telemetry_started:
            return

        if not status["wifi_ok"]:
            return

        try:
            from src.app.telemetry_state import TelemetryState
            telemetry = TelemetryState(
                air_sensor=air,
                rtc_info_getter=lambda: rtc,
                wifi_manager=wifi,
            )
            telemetry_started = True
            print("[TELEMETRY] Started.")
        except Exception as e:
            print("[TELEMETRY] Failed to start:", repr(e))

    def tick_telemetry(cfg):
        nonlocal status

        if not telemetry:
            return

        try:
            # Expect TelemetryState.tick to return True if sent,
            # False if failed, None if nothing due.
            result = telemetry.tick(cfg, rtc_dict=rtc)

            if result is True:
                if not status["api_ok"]:
                    print("[TELEMETRY] Send OK")
                status["api_ok"] = True

            elif result is False:
                if status["api_ok"]:
                    print("[TELEMETRY] Send FAILED")
                status["api_ok"] = False

        except Exception as e:
            print("[TELEMETRY] Tick error:", repr(e))
            status["api_ok"] = False

    # ------------------------------------------------------------
    # SCREEN CACHE
    # ------------------------------------------------------------

    screens = {}

    def get_screen(name):
        if name in screens:
            return screens[name]

        try:
            if name == "device":
                from src.ui.screens.device import DeviceScreen
                screens[name] = DeviceScreen(oled)
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
            elif name == "co2":
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
            elif name == "selfdestruct":
                from src.ui.screens.selfdestruct import SelfDestructScreen
                screens[name] = SelfDestructScreen(oled)
            else:
                screens[name] = None
        except Exception:
            screens[name] = None

        _gc()
        return screens[name]

    # ============================================================
    # MAIN LOOP
    # ============================================================

    while True:

        cfg = load_config() or {}

        # --- WiFi live refresh ---
        try:
            status["wifi_ok"] = bool(wifi.is_connected())
        except Exception:
            status["wifi_ok"] = False

        # --- GPS detection ---
        try:
            if cfg.get("gps_enabled", False):
                _probe_gps()
                status["gps_on"] = gps_detected
            else:
                status["gps_on"] = False
        except Exception:
            status["gps_on"] = False

        # --- Telemetry start ---
        start_telemetry_if_ready(cfg)

        # ========================================================
        # Idle callback (runs while waiting screen blocks)
        # ========================================================

        def _idle(now_ms):
            try:
                status["wifi_ok"] = bool(wifi.is_connected())
            except Exception:
                status["wifi_ok"] = False

            start_telemetry_if_ready(cfg)
            tick_telemetry(cfg)

        # --- Waiting screen ---
        action = waiting.show_live(
            oled,
            btn,
            line="Know your air...",
            animate=False,
            wifi_ok=status["wifi_ok"],
            gps_on=status["gps_on"],
            api_ok=status["api_ok"],
            on_idle=_idle,
            idle_every_ms=500,
        )

        if action:
            print("[CLICK]", action)

        # --- Click routing ---
        if action == "triple":
            connectivity_carousel(
                btn, oled, status, cfg, wifi,
                None, None, gps,
                get_screen,
            )
            continue

        if action == "single":
            sensor_carousel(btn, oled, air, get_screen)
            continue

        if action == "double":
            time_flow(btn, oled, rtc, get_screen)
            continue

        if action == "quad":
            selfdestruct_flow(btn, oled, get_screen)
            continue

        if action == "debug":
            machine.reset()

        _reset_and_flush(btn)
        _gc()
