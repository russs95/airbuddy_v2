# src/input/button.py  (MicroPython / Pico W)
import time
from machine import Pin


class AirBuddyButton:
    """
    Safe, blocking + non-blocking button handler for Pico W.

    Features:
      - Long-press debug escape (default: 2s)
      - Single / double / triple click
      - Debounced
      - REPL-safe
      - Non-blocking poll_action() for animated screens
    """

    def __init__(
            self,
            gpio_pin=15,
            click_window_s=1.0,
            debounce_ms=50,
            debug_hold_ms=2000,
    ):
        self.pin = Pin(gpio_pin, Pin.IN, Pin.PULL_UP)

        self.click_window_ms = int(float(click_window_s) * 1000)
        self.debounce_ms = int(debounce_ms)
        self.debug_hold_ms = int(debug_hold_ms)

        # --- Non-blocking state ---
        self._last_level = self.pin.value()
        self._stable_level = self._last_level
        self._last_change_ms = time.ticks_ms()

        self._press_start_ms = None
        self._click_count = 0
        self._click_window_start_ms = None

    # --------------------------------------------------
    # Low-level helpers
    # --------------------------------------------------

    def _pressed(self):
        return self.pin.value() == 0

    def _released(self):
        return self.pin.value() == 1

    def _wait_for_level(self, level, timeout_ms=None):
        """
        Wait until pin reads `level`.
        Returns True if reached, False if timed out.
        """
        start = time.ticks_ms()
        while True:
            if self.pin.value() == level:
                return True
            if timeout_ms is not None:
                if time.ticks_diff(time.ticks_ms(), start) >= timeout_ms:
                    return False
            time.sleep_ms(5)

    # --------------------------------------------------
    # NEW: Non-blocking event poll
    # --------------------------------------------------

    def poll_action(self):
        """
        Non-blocking.

        Returns:
          "debug", "single", "double", "triple" or None

        Behavior:
          - debug: emitted while held
          - double/triple: emitted immediately on release
          - single: emitted when click window expires
        """
        now = time.ticks_ms()
        level = self.pin.value()

        # Track raw transitions for debounce timing
        if level != self._last_level:
            self._last_level = level
            self._last_change_ms = now

        # Debounce: only accept change if stable
        if level != self._stable_level:
            if time.ticks_diff(now, self._last_change_ms) >= self.debounce_ms:
                self._stable_level = level

                # ---------- STABLE EDGE ----------
                if self._stable_level == 0:
                    # pressed
                    self._press_start_ms = now

                else:
                    # released
                    if self._press_start_ms is not None:
                        held_ms = time.ticks_diff(now, self._press_start_ms)
                        self._press_start_ms = None

                        # short press = click
                        if held_ms < self.debug_hold_ms:
                            if self._click_count == 0:
                                self._click_window_start_ms = now
                            self._click_count += 1

                            # 🔥 IMMEDIATE EMIT FOR DOUBLE / TRIPLE
                            if self._click_count == 2:
                                self._click_count = 0
                                self._click_window_start_ms = None
                                return "double"

                            if self._click_count >= 3:
                                self._click_count = 0
                                self._click_window_start_ms = None
                                return "triple"

        # ---------- DEBUG HOLD ----------
        if self._stable_level == 0 and self._press_start_ms is not None:
            if time.ticks_diff(now, self._press_start_ms) >= self.debug_hold_ms:
                self._press_start_ms = None
                self._click_count = 0
                self._click_window_start_ms = None
                return "debug"

        # ---------- SINGLE CLICK (DELAYED) ----------
        if self._click_count == 1 and self._click_window_start_ms is not None:
            if time.ticks_diff(now, self._click_window_start_ms) >= self.click_window_ms:
                self._click_count = 0
                self._click_window_start_ms = None
                return "single"

        return None


    # Keep a compatibility alias if you want to call it poll()
    def poll(self):
        """
        Back-compat alias: returns an action or None.
        """
        return self.poll_action()

    # --------------------------------------------------
    # Blocking API (unchanged behavior)
    # --------------------------------------------------

    def wait_for_action(self):
        """
        Blocking call.

        Returns:
            "debug", "single", "double", "triple"
        """

        # --- Wait for first press (block) ---
        self._wait_for_level(0)
        time.sleep_ms(self.debounce_ms)

        # --- Long-press debug detection ---
        press_start = time.ticks_ms()
        while self._pressed():
            if time.ticks_diff(time.ticks_ms(), press_start) >= self.debug_hold_ms:
                # Wait for release to avoid retrigger
                while self._pressed():
                    time.sleep_ms(10)
                time.sleep_ms(self.debounce_ms)
                return "debug"
            time.sleep_ms(10)

        # First press released
        time.sleep_ms(self.debounce_ms)

        # --- Click counting ---
        click_count = 1
        start = time.ticks_ms()

        while click_count < 3:
            elapsed = time.ticks_diff(time.ticks_ms(), start)
            remaining = self.click_window_ms - elapsed
            if remaining <= 0:
                break

            if not self._wait_for_level(0, timeout_ms=remaining):
                break

            time.sleep_ms(self.debounce_ms)
            self._wait_for_level(1)
            time.sleep_ms(self.debounce_ms)
            click_count += 1

        if click_count == 1:
            return "single"
        if click_count == 2:
            return "double"
        return "triple"

    def reset(self):
        now=time.ticks_ms()
        lvl=self.pin.value()
        self._last_level=lvl
        self._stable_level=lvl
        self._last_change_ms=now
        self._press_start_ms=None
        self._click_count=0
        self._click_window_start_ms=None

