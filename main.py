# main.py (device root) — AirBuddy 2.1 launcher
try:
    from src.app.main import run
    run()
except Exception as e:
    # Always print something helpful in REPL if boot fails
    print("AirBuddy boot error:", repr(e))
    raise
