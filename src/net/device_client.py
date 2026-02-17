# src/net/device_client.py
# Device lookup / check-in client (Pico / MicroPython safe)

import gc
import ujson

try:
    import urequests as requests
except Exception:
    requests = None


def _trim_base(api_base):
    s = (api_base or "").strip()
    while s.endswith("/"):
        s = s[:-1]
    return s


def lookup_device_compact(api_base, device_id, device_key, timeout_s=6):
    """
    Calls:
      GET {api_base}/api/v1/device?compact=1

    Returns:
      (ok: bool, data: dict|None, err: str|None)

    Memory safe:
    - gc.collect() before + after
    - never uses response.json()
    - always closes response
    """
    if requests is None:
        return (False, None, "urequests_unavailable")

    api_base = _trim_base(api_base)
    if not api_base:
        return (False, None, "missing_api_base")

    url = api_base + "/api/v1/device?compact=1"
    headers = {
        "X-Device-Id": device_id,
        "X-Device-Key": device_key,
        "Accept": "application/json",
        "Connection": "close",
    }

    gc.collect()
    r = None
    try:
        # IMPORTANT: timeout support depends on urequests build.
        # If your build doesn't accept timeout=, remove it.
        try:
            r = requests.get(url, headers=headers, timeout=timeout_s)
        except TypeError:
            r = requests.get(url, headers=headers)

        status = getattr(r, "status_code", None)
        if status != 200:
            # read a tiny bit for diagnostics without holding big strings
            try:
                txt = r.text
                if txt and len(txt) > 120:
                    txt = txt[:120]
            except Exception:
                txt = ""
            return (False, None, "http_%s_%s" % (status, txt))

        # Avoid r.json() (RAM heavy). Use ujson on text.
        try:
            txt = r.text  # may allocate; compact response keeps it small
        except Exception:
            txt = None

        if not txt:
            return (False, None, "empty_body")

        try:
            data = ujson.loads(txt)
        except Exception:
            return (False, None, "bad_json")

        if not isinstance(data, dict) or not data.get("ok"):
            return (False, None, "not_ok")

        # Extract only what you need (reduces long-lived RAM)
        out = {
            "device_name": None,
            "home_name": None,
            "room_name": None,
            "community_name": None,
            "user_name": None,
        }

        try:
            dev = data.get("device") or {}
            out["device_name"] = dev.get("device_name")

            a = data.get("assignment") or {}
            h = a.get("home") or {}
            rm = a.get("room") or {}
            c = a.get("community") or {}
            u = a.get("user") or {}

            out["home_name"] = h.get("home_name")
            out["room_name"] = rm.get("room_name")
            out["community_name"] = c.get("com_name")
            out["user_name"] = u.get("full_name")
        except Exception:
            pass

        return (True, out, None)

    except MemoryError:
        return (False, None, "mem_error")
    except OSError as e:
        # OSError(12) is typically ENOMEM
        return (False, None, "os_error_%s" % (e,))
    except Exception as e:
        return (False, None, "err_%s" % (e,))
    finally:
        if r is not None:
            try:
                r.close()
            except Exception:
                pass
        gc.collect()
