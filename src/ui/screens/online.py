# src/ui/screens/online.py

from src.app.config import load_config
from src.net.telemetry_client import TelemetryClient
from src.net.wifi_manager import WiFiManager


class OnlineScreen:

    def __init__(self, oled):
        self.oled = oled
        self.cfg = load_config()
        self.wifi = WiFiManager()

        self.client = TelemetryClient(
            api_base="https://air.earthen.io",
            device_id=self.cfg.get("device_id"),
            device_key=self.cfg.get("device_key")
        )

        self._status = ""

    # ----------------------------
    # Drawing
    # ----------------------------
    def _draw(self):
        o = self.oled
        fb = o.oled
        fb.fill(0)

        o.f_arvo20.write("Online", 0, 0)

        o.f_med.write(self._status[:18], 0, 28)

        fb.show()

    # ----------------------------
    # Handshake
    # ----------------------------
    def _handshake(self):
        if not self.wifi.is_connected():
            self._status = "No WiFi"
            return

        # Send minimal test payload
        payload = {
            "ping": True
        }

        ok, msg = self.client.send(payload)

        if ok:
            self._status = "Online OK"
        else:
            self._status = "Queued"

    # ----------------------------
    # Public
    # ----------------------------
    def show_live(self, btn):
        btn.reset()

        self._status = "Testing..."
        self._draw()

        self._handshake()
        self._draw()

        while True:
            action = btn.wait_for_action()

            if action == "single":
                return "next"

            if action == "double":
                self._status = "Retry..."
                self._draw()
                self._handshake()
                self._draw()
