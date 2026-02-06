# button.py
from machine import Pin
import time

class Button:
    """
    Simple debounced active-low button (button wired to GND).
    - Uses internal pull-up.
    - call .pressed() to poll
    - call .wait_for_press() to block until press
    """

    def __init__(self, gpio, pull=Pin.PULL_UP, debounce_ms=40):
        self.pin = Pin(gpio, Pin.IN, pull)
        self.debounce_ms = debounce_ms
        self._last = self.pin.value()
        self._last_change = time.ticks_ms()

    def _stable_read(self):
        v = self.pin.value()
        now = time.ticks_ms()
        if v != self._last:
            self._last = v
            self._last_change = now
        # stable if unchanged for debounce window
        if time.ticks_diff(now, self._last_change) >= self.debounce_ms:
            return self._last
        return None

    def pressed(self):
        """
        Returns True exactly when stable state is pressed (0).
        Non-blocking; may return False often.
        """
        v = self._stable_read()
        return (v == 0)

    def wait_for_press(self, poll_ms=10):
        """
        Blocks until a press is detected (stable 0),
        then waits for release to avoid double-trigger.
        """
        while True:
            v = self._stable_read()
            if v == 0:
                break
            time.sleep_ms(poll_ms)

        # wait for release
        while True:
            v = self._stable_read()
            if v == 1:
                break
            time.sleep_ms(poll_ms)
        return True
