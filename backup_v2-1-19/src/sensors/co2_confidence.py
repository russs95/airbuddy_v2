# src/sensors/co2_confidence.py
# Pico-safe confidence model for ENS160 eCO2 readings

def clamp(val, lo=0, hi=100):
    if val < lo:
        return lo
    if val > hi:
        return hi
    return val


def calculate_co2_confidence(
        *,
        ens_valid,
        warmup_done,
        temp_ok,
        rh_ok,
        eco2_ppm,
        last_eco2_ppm=None,
        aqi=None,
        last_aqi=None,
        source="button",
):
    """
    Returns confidence 1–100 for an eCO2 reading.
    """

    score = 0

    # --- ENS160 data validity (30) ---
    if ens_valid:
        score += 30

    # --- Warmup completed (10) ---
    if warmup_done:
        score += 10

    # --- Temperature / RH compensation (10 + 10) ---
    if temp_ok:
        score += 10
    if rh_ok:
        score += 10

    # --- eCO2 stability (20) ---
    if last_eco2_ppm is not None:
        delta = abs(eco2_ppm - last_eco2_ppm)
        if delta < 50:
            score += 20
        elif delta < 150:
            score += 12
        elif delta < 300:
            score += 5
    else:
        score += 5  # first reading baseline

    # --- AQI stability (15) ---
    if aqi is not None and last_aqi is not None:
        if abs(aqi - last_aqi) <= 1:
            score += 15
        else:
            score += 5

    # --- Source penalty (5) ---
    if source != "fallback":
        score += 5

    return clamp(score, 1, 100)
