#src/app/gps_init.py

def init_gps(uart_id=1,baud=9600,tx_pin=8,rx_pin=9):
    try:
        from src.sensors.ublox6gps import Ublox6GPS
        return Ublox6GPS(uart_id=uart_id,baud=baud,tx_pin=tx_pin,rx_pin=rx_pin)
    except Exception as e:
        print("GPS:init skipped:",repr(e))
        return None
