# src/ui/headless.py
import sys
import time

class HeadlessDisplay:
    """
    Drop-in replacement for OLED when hardware isn't attached.
    Does not crash. Writes updates to stdout.
    """

    def __init__(self):
        self.width = 128
        self.height = 64

    def clear(self):
        pass

    def show_waiting(self, message="Know your air..."):
        print(f"[UI] {message}", flush=True)

    def show_spinner_frame(self, *args, **kwargs):
        # Avoid spamming the console; print occasionally if you want.
        pass

    def show_results(self, temp_c, eco2_ppm, tvoc_ppb, rating="Ok", humidity=None, cached=False):
        tag = " (cached)" if cached else ""
        hum = f", Hum: {humidity:.1f}%" if humidity is not None else ""
        print(f"[RESULT]{tag} Temp: {temp_c:.1f}C{hum}, eCO2: {eco2_ppm}ppm, TVOC: {tvoc_ppb}ppb, Air: {rating}", flush=True)

    def show_face(self, rating):
        print(f"[FACE] {rating}", flush=True)

    def draw_centered(self, *args, **kwargs):
        pass
