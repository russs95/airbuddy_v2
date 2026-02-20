# src/ui/screens/gps.py

import time
import json
from src.ui.toggle import ToggleSwitch

CONFIG_FILE = "config.json"


class GPSScreen:
    def __init__(self, oled):
        self.oled = oled
        self.toggle = ToggleSwitch(x=100, y=6, w=24, h=52)

        self.enabled = False
        self.last_fix = False
        self.last_lat = None
        self.last_lon = None
        self.last_sats = None

        self._load_config()

    # ----------------------------
    # tiny safe writer helper
    # ----------------------------
    def _w(self, writer, text, x, y):
        try:
            writer.write(text, int(x), int(y))
        except Exception:
            pass

    # ----------------------------
    # Config persistence
    # ----------------------------
    def _load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            self.enabled = bool(cfg.get("gps_enabled", False))
        except Exception:
            self.enabled = False

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({"gps_enabled": self.enabled}, f)
        except Exception:
            pass

    # ----------------------------
    # Parsing helpers
    # ----------------------------
    def _nmea_degmin_to_deg(self, s, hemi):
        try:
            if not s or not hemi:
                return None
            dot = s.find(".")
            if dot < 0:
                return None
            deg_len = 2 if hemi in ("N", "S") else 3
            deg = int(s[:deg_len])
            minutes = float(s[deg_len:])
            val = deg + (minutes / 60.0)
            if hemi in ("S", "W"):
                val = -val
            return val
        except Exception:
            return None

    def _parse_rmc(self, line):
        try:
            p = line.split(",")
            if len(p) < 7:
                return
            self.last_fix = (p[2] == "A")

            if p[3] and p[4] and p[5] and p[6]:
                lat = self._nmea_degmin_to_deg(p[3], p[4])
                lon = self._nmea_degmin_to_deg(p[5], p[6])
                if lat is not None and lon is not None:
                    self.last_lat = lat
                    self.last_lon = lon
        except Exception:
            pass

    def _parse_gga(self, line):
        try:
            p = line.split(",")
            if len(p) < 8:
                return

            if p[6] and p[6] != "0":
                self.last_fix = True

            if p[7]:
                try:
                    self.last_sats = int(p[7])
                except Exception:
                    pass

            if p[2] and p[3] and p[4] and p[5]:
                lat = self._nmea_degmin_to_deg(p[2], p[3])
                lon = self._nmea_degmin_to_deg(p[4], p[5])
                if lat is not None and lon is not None:
                    self.last_lat = lat
                    self.last_lon = lon
        except Exception:
            pass

    def _clear_data(self):
        self.last_fix = False
        self.last_lat = None
        self.last_lon = None
        self.last_sats = None

    def _consume_once(self, gps, max_ms=200):
        try:
            t = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t) < int(max_ms):
                line = gps.read_nmea(max_ms=30)
                if not line:
                    return
                if "RMC" in line:
                    self._parse_rmc(line)
                elif "GGA" in line:
                    self._parse_gga(line)
        except Exception:
            pass

    # ----------------------------
    # Drawing
    # ----------------------------
    def _draw(self):
        o = self.oled
        fb = o.oled
        fb.fill(0)

        title_writer = o.f_arvo20
        self._w(title_writer, "GPS", 0, 0)

        try:
            _, title_h = o._text_size(title_writer, "Ag")
        except Exception:
            title_h = 20

        data_y0 = int(title_h + 4)
        data_writer = o.f_med

        try:
            _, h_med = o._text_size(data_writer, "Ag")
        except Exception:
            h_med = 12

        line_h = int(h_med + 2)

        y1 = data_y0
        y2 = y1 + line_h
        y3 = y2 + line_h

        if self.enabled and self.last_fix and self.last_lat and self.last_lon:
            self._w(data_writer, "LAT:{:.5f}".format(self.last_lat), 0, y1)
            self._w(data_writer, "LON:{:.5f}".format(self.last_lon), 0, y2)
        else:
            self._w(data_writer, "LAT: --", 0, y1)
            self._w(data_writer, "LON: --", 0, y2)

        sats = "--"
        if self.enabled and self.last_sats is not None:
            sats = str(int(self.last_sats))

        self._w(data_writer, "SATS: " + sats, 0, y3)

        self.toggle.draw(fb, on=self.enabled)
        fb.show()

    # ----------------------------
    # Public entry
    # ----------------------------
    def show_live(self, gps, btn):
        """
        Single click: go to next settings screen (WiFi)
        Double click: toggle GPS
        """

        btn.reset()

        # 🔥 HARDWARE CHECK
        if not gps:
            # Force OFF if hardware not present
            if self.enabled:
                self.enabled = False
                self._save_config()
            self._clear_data()
            self._draw()

        else:
            if self.enabled:
                try:
                    gps.enable()
                except Exception:
                    pass
                self._consume_once(gps, max_ms=250)
            else:
                try:
                    gps.disable()
                except Exception:
                    pass

            self._draw()

        while True:
            action = btn.wait_for_action()

            if action == "single":
                return "single"

            if action == "double":
                # 🔥 Prevent enabling if no hardware
                if not gps:
                    continue

                self.enabled = not self.enabled
                self._save_config()

                if self.enabled:
                    try:
                        gps.enable()
                    except Exception:
                        pass
                    self._consume_once(gps, max_ms=300)
                else:
                    try:
                        gps.disable()
                    except Exception:
                        pass
                    self._clear_data()

                self._draw()
