"""
AirBuddy 2.1 Font Registry

Semantic font roles:
- VSMALL  : version numbers, status text, tiny UI hints (sans-serif)
- SMALL   : secondary labels, compact UI text (sans-serif)
- MED     : primary labels (Temperature, eCO2, Humidity)
- LARGE   : hero numbers + title text (time, ppm, °C, "airBuddy")
- SYMBOLS : bars, blocks, icons, UI glyphs
"""

# --- Font data modules (ezFBfont compatible) ---

# Symbols / blocks / extended glyphs
from . import ezFBfont_amstrad_cpc_extended_supp_08 as SYMBOLS

# Sans-serif text fonts
from . import ezFBfont_PTSansNarrow_06_ascii_08 as VSMALL
from . import ezFBfont_PTSansNarrow_07_ascii_11 as SMALL
from . import ezFBfont_PTSansNarrow_10_ascii_14 as MED

# Serif / hero font (time, big numbers, title)
from . import ezFBfont_ncenB24_time_24 as LARGE


# --- Registry helpers ---

_REGISTRY = {
    "vsmall": VSMALL,
    "small": SMALL,
    "med": MED,
    "medium": MED,
    "large": LARGE,
    "hero": LARGE,
    "symbols": SYMBOLS,
}

def get(name: str):
    """Return a font module by semantic name."""
    key = (name or "").strip().lower()
    if key not in _REGISTRY:
        raise KeyError(
            "Unknown font '{}'. Available: {}".format(
                name, ", ".join(sorted(_REGISTRY.keys()))
            )
        )
    return _REGISTRY[key]

def list_fonts():
    """Return available font modules."""
    return dict(_REGISTRY)
