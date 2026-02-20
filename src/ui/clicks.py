# src/ui/clicks.py — Click / dwell / button helpers (MicroPython / Pico-safe)
#
# Purpose:
# - Keep AirBuddy click handling utilities out of app/main.py
# - All functions are defensive: never crash if btn/oled are None or missing methods

import time


WAIT_POLL_MS = 25


def gc_collect():
    try:
        import gc
        gc.collect()
    except Exception:
        pass


def flush_actions(btn, ms=250, poll_ms=WAIT_POLL_MS):
    """
    Drain any queued click actions for up to ms.
    """
    if btn is None:
        return
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < int(ms):
        try:
            btn.poll_action()
        except Exception:
            pass
        time.sleep_ms(int(poll_ms))


def wait_release(btn):
    """
    Typical pull-up button: pressed=0, released=1.
    """
    if btn is None:
        return
    try:
        while btn.pin.value() == 0:
            time.sleep_ms(10)
    except Exception:
        pass


def wait_for_single(btn, poll_ms=WAIT_POLL_MS):
    """
    Blocks until a SINGLE click is detected.
    Returns other actions if they occur ("double"/"triple"/"quad"/"debug").
    """
    while True:
        try:
            a = btn.poll_action()
        except Exception:
            a = None
        if a == "single":
            return a
        if a in ("double", "triple", "quad", "debug"):
            return a
        time.sleep_ms(int(poll_ms))


def dwell_or_click(btn, dwell_ms, poll_ms=WAIT_POLL_MS):
    """
    Wait up to dwell_ms, but return early if any click action arrives.
    Returns: None (timeout) or action string.
    """
    if btn is None:
        time.sleep_ms(int(dwell_ms))
        return None

    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < int(dwell_ms):
        try:
            a = btn.poll_action()
        except Exception:
            a = None
        if a is not None:
            return a
        time.sleep_ms(int(poll_ms))
    return None


def reset_and_flush(btn, flush_ms=250, poll_ms=WAIT_POLL_MS):
    """
    Convenience: btn.reset() (if available) then flush.
    """
    if btn is None:
        return
    try:
        btn.reset()
    except Exception:
        pass
    flush_actions(btn, ms=flush_ms, poll_ms=poll_ms)


def draw_text(oled, text, y=24):
    """
    Ultra-safe text draw helper (no extra imports).
    Expects oled to be your OLED wrapper (with oled.oled FrameBuffer and fonts).
    """
    if oled is None:
        return
    try:
        fb = getattr(oled, "oled", None)
        if fb is None:
            return
        fb.fill(0)

        writer = getattr(oled, "f_med", None) or getattr(oled, "f_small", None)
        if writer:
            try:
                w, _ = writer.size(text)
                x = max(0, (getattr(oled, "width", 128) - w) // 2)
            except Exception:
                x = 0
            writer.write(text, x, int(y))

        fb.show()
    except Exception:
        pass
