# src/ui/flows.py — Screen flow logic for AirBuddy

import time
from src.ui.clicks import (
    draw_text,
    wait_for_single,
    wait_release,
    dwell_or_click,
    reset_and_flush,
    gc_collect,
)


# ============================================================
# CONNECTIVITY CAROUSEL (TRIPLE CLICK)
# ============================================================

def connectivity_carousel(
        btn,
        oled,
        status,
        cfg,
        wifi,
        api_boot,
        wifi_boot,
        gps,
        get_screen,
        selfdestruct_cb=None,
        flush_ms=250,
        poll_ms=25,
):
    """
    Triple-click flow:

    Waiting
       ↓ (triple)
    Device Screen
       ↓ (single)
    GPS Screen (if enabled)
       ↓ (single)
    WiFi Screen   (ALWAYS)
       ↓ (single)
    Online Screen
       ↓ (single)
    Logging Screen
       ↓ (single)
    Waiting

    Notes:
    - Never blocks just because nothing is connected.
    - Quad click triggers selfdestruct_cb (if provided) or returns "quad".
    """

    # Optional: show a "please connect" screen FIRST if nothing is connected,
    # but DO NOT block the rest of the flow.
    try:
        nothing_connected = (not status.get("wifi_ok")) and (not status.get("gps_on")) and (not status.get("api_ok"))
    except Exception:
        nothing_connected = True

    if nothing_connected:
        pc = get_screen("please_connect")
        if pc and hasattr(pc, "show_live"):
            try:
                a0 = pc.show_live(btn=btn)
            except Exception:
                a0 = wait_for_single(btn)
        else:
            draw_text(oled, "PLEASE CONNECT", y=24)
            a0 = wait_for_single(btn)

        if a0 == "quad":
            if selfdestruct_cb:
                selfdestruct_cb()
                reset_and_flush(btn, flush_ms, poll_ms)
                return
            reset_and_flush(btn, flush_ms, poll_ms)
            return "quad"

        # single continues into the real flow
        reset_and_flush(btn, flush_ms, poll_ms)

    # Build the required order
    order = ["device"]

    # GPS only if enabled in config (NOT “detected”)
    try:
        gps_enabled = bool(cfg.get("gps_enabled", False))
    except Exception:
        gps_enabled = False

    if gps_enabled:
        order.append("gps")

    # WiFi ALWAYS in this flow
    order += ["wifi", "online", "logging"]

    # Run flow
    for name in order:

        scr = get_screen(name)

        if scr is None:
            draw_text(oled, name.upper(), y=24)
            a = wait_for_single(btn)

        else:
            if hasattr(scr, "show_live"):
                try:
                    if name == "device":
                        a = scr.show_live(btn=btn, api_boot=api_boot, wifi_boot=wifi_boot)

                    elif name == "gps":
                        a = scr.show_live(btn=btn, gps=gps)
                    elif name == "wifi":
                        a = scr.show_live(btn=btn, wifi=wifi, cfg_getter=lambda: cfg)
                    elif name == "online":
                        a = scr.show_live(btn=btn, cfg_getter=lambda: cfg)
                    elif name == "logging":
                        a = scr.show_live(btn=btn, cfg_getter=lambda: cfg, wifi=wifi)
                    else:
                        a = scr.show_live(btn=btn)
                except Exception:
                    a = wait_for_single(btn)
            else:
                try:
                    if hasattr(scr, "show"):
                        scr.show()
                except Exception:
                    pass
                a = wait_for_single(btn)

        # Special actions
        if a == "quad":
            if selfdestruct_cb:
                selfdestruct_cb()
                reset_and_flush(btn, flush_ms, poll_ms)
                return
            reset_and_flush(btn, flush_ms, poll_ms)
            return "quad"

        # Anything but single exits back to waiting
        if a != "single":
            reset_and_flush(btn, flush_ms, poll_ms)
            return a

        reset_and_flush(btn, flush_ms, poll_ms)

    # Done → back to waiting

# ============================================================
# SENSOR CAROUSEL (SINGLE CLICK)
# ============================================================

def sensor_carousel(
        btn,
        oled,
        air,
        get_screen,
        dwell_ms=4000,
        flush_ms=250,
        poll_ms=25,
):
    if air is None:
        draw_text(oled, "NO SENSOR", y=24)
        wait_for_single(btn)
        return

    # One full reading for CO2/TVOC screens
    try:
        reading = air.finish_sampling(log=False)
    except Exception as e:
        print("[FLOW] finish_sampling error:", repr(e))
        return

    gc_collect()
    reset_and_flush(btn, flush_ms, poll_ms)

    for name in ("co2", "tvoc", "temp"):
        scr = get_screen(name)
        if not scr:
            print("[FLOW] screen missing:", name)
            continue

        try:
            # ------------------------------------------------
            # TEMP: if you implemented a live-refresh temp screen,
            # use it (it will block until single click).
            # ------------------------------------------------
            if name == "temp" and hasattr(scr, "show_live"):
                try:
                    # show_live should refresh internally every ~4s and exit on single click
                    # (your temp.py update request)
                    return scr.show_live(btn=btn, air=air)
                except TypeError:
                    # Fallback if your show_live signature differs
                    return scr.show_live(btn=btn)

            # Default: simple show(reading)
            scr.show(reading)

        except Exception as e:
            print("[FLOW] screen error:", name, repr(e))
            # DO NOT silently skip — show a visible placeholder so you notice
            draw_text(oled, "ERR " + name.upper(), y=24)
            wait_for_single(btn)
            reset_and_flush(btn, flush_ms, poll_ms)
            return

        wait_release(btn)

        a = dwell_or_click(btn, dwell_ms, poll_ms)

        # timeout → advance to next screen
        if a is None:
            reset_and_flush(btn, flush_ms=min(120, flush_ms), poll_ms=poll_ms)
            continue

        # single → advance to next screen
        if a == "single":
            reset_and_flush(btn, flush_ms=min(180, flush_ms), poll_ms=poll_ms)
            continue

        # any other action exits carousel
        reset_and_flush(btn, flush_ms, poll_ms)
        return a

    # Summary at end
    summ = get_screen("summary")
    if summ and hasattr(summ, "show_live"):
        try:
            summ.show_live(get_reading=lambda: reading, btn=btn)
        except Exception as e:
            print("[FLOW] summary error:", repr(e))
    else:
        draw_text(oled, "SUMMARY", y=24)
        wait_for_single(btn)

    reset_and_flush(btn, flush_ms, poll_ms)

# ============================================================
# TIME FLOW (DOUBLE CLICK)
# ============================================================

def time_flow(btn, oled, rtc, get_screen, flush_ms=250, poll_ms=25):

    ts = get_screen("time")

    if ts and hasattr(ts, "show_live"):
        try:
            from src.app.sysinfo import get_time_str, get_date_str

            ts.show_live(
                get_date_str=get_date_str,
                get_time_str=get_time_str,
                get_source=lambda: "RTC",
                get_temp_c=lambda: rtc.get("temp_c") if isinstance(rtc, dict) else None,
                btn=btn,
                max_seconds=0,
            )
            return
        except Exception:
            pass

    draw_text(oled, "TIME", y=24)
    wait_for_single(btn)
    reset_and_flush(btn, flush_ms, poll_ms)


# ============================================================
# SELF DESTRUCT (QUAD CLICK)
# ============================================================

def selfdestruct_flow(btn, oled, get_screen, flush_ms=250, poll_ms=25):

    scr = get_screen("selfdestruct")

    if scr and hasattr(scr, "run"):
        try:
            scr.run()
        except Exception:
            pass
    else:
        draw_text(oled, "SELFDESTRUCT", y=20)
        time.sleep_ms(800)

    draw_text(oled, "DONE", y=28)
    wait_for_single(btn)
    reset_and_flush(btn, flush_ms, poll_ms)
