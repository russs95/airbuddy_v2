# src/ui/screens/gps.py  (MicroPython / Pico-safe)

import time
import gc

from src.ui.toggle import ToggleSwitch

try:
    from src.ui import connection_header as _ch
    from src.ui.connection_header import GPS_NONE, GPS_INIT, GPS_FIXED
except Exception:
    _ch = None
    GPS_NONE = 0
    GPS_INIT = 1
    GPS_FIXED = 2


class GPSScreen:
    def __init__(self, oled):
        self.oled = oled

        self._top_pad = 5

        # Smaller toggle — same geometry as WiFi screen
        w = int(getattr(oled, "width", 128))
        h = int(getattr(oled, "height", 64))

        tx = 100
        ty = 16 + self._top_pad
        tw = 24
        th = 40

        if tx + tw > w:
            tw = max(1, w - tx)
        if ty + th > h:
            th = max(1, h - ty)

        self.toggle = ToggleSwitch(x=tx, y=ty, w=tw, h=th)

        self.enabled = False
        self.last_fix = False
        self.last_lat = None
        self.last_lon = None
        self.last_sats = None

        # "Checking GPS..." animation state
        self._checking = False
        self._dot_phase = 0
        self._next_anim_ms = 0
        self._check_pending = False
        self._next_check_ms = 0
        self._status = ""

        self._load_config()

    # ----------------------------
    # Config
    # ----------------------------

    def _load_config(self):
        try:
            from config import load_config
            cfg = load_config() or {}
            self.enabled = bool(cfg.get("gps_enabled", False))
        except Exception:
            self.enabled = False

    def _save_config(self):
        try:
            from config import load_config, save_config
            cfg = load_config() or {}
            cfg["gps_enabled"] = self.enabled
            save_config(cfg)
        except Exception:
            pass

    # ----------------------------
    # NMEA parsing helpers
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

    def _consume_once(self, gps, max_ms=800):
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
    # Checking animation
    # ----------------------------

    def _set_checking(self, on):
        self._checking = bool(on)
        if on:
            self._dot_phase = 0
            self._next_anim_ms = time.ticks_ms()

    def _tick_checking(self):
        if not self._checking:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_anim_ms) < 0:
            return
        self._next_anim_ms = time.ticks_add(now, 400)
        self._dot_phase = (self._dot_phase + 1) % 4
        dots = "." * self._dot_phase
        self._status = "Checking GPS" + dots
        self._draw()

    # ----------------------------
    # GPS probe
    # ----------------------------

    def _do_check(self, gps):
        """Try to read NMEA data to confirm GPS hardware is present."""
        if not gps:
            return
        try:
            gps.enable()
        except Exception:
            pass
        gc.collect()
        self._consume_once(gps, max_ms=800)

    # ----------------------------
    # Drawing
    # ----------------------------

    def _draw(self):
        o = self.oled
        fb = o.oled
        fb.fill(0)

        # Connectivity icons: top-right (GPS state)
        if _ch:
            try:
                if self._checking:
                    gps_state = GPS_INIT
                elif self.last_fix:
                    gps_state = GPS_FIXED
                else:
                    gps_state = GPS_NONE
                _ch.draw(
                    fb,
                    o.width,
                    gps_state=gps_state,
                    wifi_ok=False,
                    api_connected=False,
                    api_sending=False,
                    icon_y=1,
                )
            except Exception:
                pass

        # Title
        title_y = self._top_pad
        o.f_arvo20.write("GPS", 0, title_y)

        try:
            _, title_h = o._text_size(o.f_arvo20, "Ag")
        except Exception:
            title_h = 20

        data_y = int(title_y + title_h + 4)
        line_h = 13

        # Status line
        if self._checking:
            status_text = self._status
        elif not self.enabled:
            status_text = "GPS off"
        elif self.last_fix:
            status_text = "Fix acquired"
        else:
            status_text = "No fix"

        o.f_med.write(status_text[:18], 0, data_y)

        if self.enabled and not self._checking:
            if self.last_fix and self.last_lat is not None and self.last_lon is not None:
                o.f_med.write("LAT:{:.4f}".format(self.last_lat), 0, data_y + line_h)
                o.f_med.write("LON:{:.4f}".format(self.last_lon), 0, data_y + line_h * 2)
            else:
                sats = "--" if self.last_sats is None else str(int(self.last_sats))
                o.f_med.write("Sats: " + sats, 0, data_y + line_h)

        self.toggle.draw(fb, on=self.enabled)
        fb.show()

    # ----------------------------
    # Public entry
    # ----------------------------

    def show_live(self, gps, btn):
        """
        Single click: advance to next screen.
        Double click: toggle GPS enabled, re-check on enable.
        """
        btn.reset()
        self._load_config()
        self._clear_data()

        # Always probe on entry — show animated "Checking GPS..."
        self._set_checking(True)
        self._status = "Checking GPS"
        self._draw()
        self._check_pending = True
        self._next_check_ms = time.ticks_add(time.ticks_ms(), 600)

        while True:
            self._tick_checking()

            try:
                action = btn.poll_action()
            except Exception:
                action = None

            if action == "single":
                return "single"

            if action == "quad":
                return "quad"

            if action == "double":
                if not gps:
                    time.sleep_ms(25)
                    continue

                self.enabled = not self.enabled
                self._save_config()
                self._clear_data()

                if self.enabled:
                    # Re-probe after enabling
                    self._set_checking(True)
                    self._status = "Checking GPS"
                    self._draw()
                    self._check_pending = True
                    self._next_check_ms = time.ticks_add(time.ticks_ms(), 300)
                else:
                    try:
                        gps.disable()
                    except Exception:
                        pass
                    self._set_checking(False)
                    self._draw()

                btn.reset()

            if self._check_pending:
                now = time.ticks_ms()
                if time.ticks_diff(now, self._next_check_ms) >= 0:
                    self._check_pending = False
                    self._set_checking(False)
                    self._do_check(gps)
                    self._draw()

            time.sleep_ms(25)
