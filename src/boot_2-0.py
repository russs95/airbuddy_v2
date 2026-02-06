# boot.py — AirBuddy ampy-safe boot (ESP32 MicroPython)
import time, os

# Give tools time to connect
time.sleep(2)

# Dev flag: if /skip_main exists, do not auto-run anything extra.
# IMPORTANT: do NOT raise SystemExit here (can cause soft reboot loops).
try:
    if "skip_main" in os.listdir("/"):
        print("DEV MODE: /skip_main present — main.py will not run")
except Exception:
    pass
