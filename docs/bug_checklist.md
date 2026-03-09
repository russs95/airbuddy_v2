
┌──────────┬──────────────────────────────────────────────────────────────────┐
│ Priority │                              Issue                               │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ 1        │ gps_pins() unpack (4 values, not 3) — will crash on any GPS init │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ 2        │ wifi.py / logging.py if → elif (nav broken)                      │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ 3        │ flows.py wrong config key (logging_enabled → telemetry_enabled)  │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ 4        │ main.py infinite HAL-fail loop — add auto-reset                  │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ 5        │ time.py None guard on api_base                                   │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ 6        │ Wire up NullWiFiManager as the WiFi-disabled fallback            │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ 7        │ Bare except: → except Exception: in ublox6gps.py                 │
├──────────┼──────────────────────────────────────────────────────────────────┤
│ 8        │ Screen signature standardisation                                 │
└──────────┴──────────────────────────────────────────────────────────────────┘




Alternative 2 — Lazy font loading: only load fonts needed for a screen, when that screen is opened

How it works: device/src/ui/oled.py currently loads all 6 font modules eagerly in OLED.__init__. Instead, make font writers lazy properties: the writer is None until first accessed, at which point the font module is imported
and the writer created. Screen-specific fonts (e.g. arvo20 for TempScreen, arvo16 for TimeScreen) are loaded inside get_screen() just before the screen class is imported.

Files to change:
- device/src/ui/oled.py — convert self.f_arvo16, self.f_arvo20 (and optionally self.f_arvo) to lazy properties
- device/src/app/main.py get_screen() — import the relevant font before each screen import

Savings: arvo20 (~15 KB) + arvo16 (~12 KB) saved at boot time. If only f_med + f_large are pre-loaded, saves ~27 KB of contiguous heap.

Pros: Directly reduces peak RAM at the moment screens are first created. Scales: if a screen is never opened (e.g. time screen), its font is never loaded.
Cons: First open of a screen is slower (font import adds ~50–200 ms). oled.f_arvo20 callers need to handle None gracefully.

 ---
Alternative 3 — Freeze font modules into MicroPython firmware flash

How it works: MicroPython supports "frozen modules" — Python source files compiled into the firmware binary and stored in flash (ROM), not RAM. When a frozen module is imported, its byte-code and data live in flash. On ESP32,
this is accessible via irom — reading is slower than RAM but the RAM cost drops to zero.

All 6 font modules (arvo16, arvo20, arvo24, mulish14, narrow7, ezFBfont_PTSansNarrow) total ~55–70 KB in RAM. Frozen, they use 0 KB of RAM. This alone frees enough RAM to avoid all observed MemoryErrors.

How to implement:
1. Clone the micropython repo and the esp-idf toolchain.
2. Copy the font .py files into ports/esp32/modules/ (the frozen-modules directory).
3. Build with idf.py build — fonts compile into the firmware image.
4. Flash with esptool.py.

Pros: Solves the problem permanently. No code changes needed. Frees the most RAM (~55–70 KB). Standard embedded practice for tight-memory devices.
Cons: Requires setting up the ESP32 MicroPython build toolchain (significant one-time effort). Every font change requires a firmware rebuild + reflash.

 ---
Recommended Order

1. Start with Alternative 1 (pre-warm fonts) — implement in 10 minutes, likely fixes the immediate crash with zero architectural risk.
2. Add Alternative 2 (lazy arvo16/arvo20 loading) — easy follow-on, saves ~27 KB and protects against future growth.
3. Consider Alternative 3 (frozen modules) only if RAM pressure continues to grow as more features are added.

Files That Would Change

┌─────────────┬──────────────────────────────────────────────────────────┐
│ Alternative │                          Files                           │
├─────────────┼──────────────────────────────────────────────────────────┤
│ 1           │ device/main.py (or device/src/app/main.py)               │
├─────────────┼──────────────────────────────────────────────────────────┤
│ 2           │ device/src/ui/oled.py, device/src/app/main.py            │
├─────────────┼──────────────────────────────────────────────────────────┤
│ 3           │ ESP32 MicroPython port modules/ directory + build system │
└─────────────┴──────────────────────────────────────────────────────────┘