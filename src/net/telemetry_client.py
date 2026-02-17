# src/net/telemetry_client.py  (LOW-MEM, Pico-friendly)

import time

try:
    import gc
except Exception:
    gc = None

try:
    import urequests as requests
except Exception:
    requests = None

QUEUE_FILE = "telemetry_queue.json"


def _gc_collect():
    if gc:
        try:
            gc.collect()
        except Exception:
            pass


def _json():
    """Prefer ujson to reduce overhead. Fallback to json if needed."""
    try:
        import ujson as j
        return j
    except Exception:
        import json as j
        return j


class TelemetryClient:
    def __init__(self, api_base, device_id, device_key):
        self.api_base = (api_base or "").strip().rstrip("/")
        self.endpoint = self.api_base + "/api/v1/telemetry"

        self.device_id = (device_id or "").strip()
        self.device_key = (device_key or "").strip()
        self._last_error = ""

    def last_error(self):
        return self._last_error or ""

    # ----------------------------
    # Queue Handling
    # ----------------------------
    def _load_queue(self):
        j = _json()
        try:
            with open(QUEUE_FILE, "r") as f:
                q = j.load(f)
            if isinstance(q, list):
                return q
            return []
        except Exception:
            return []
        finally:
            _gc_collect()

    def _save_queue(self, q):
        j = _json()
        try:
            with open(QUEUE_FILE, "w") as f:
                j.dump(q, f)
        except Exception:
            pass
        finally:
            _gc_collect()

    def _enqueue(self, payload, max_items=100):
        q = self._load_queue()
        try:
            q.append(payload)
            if len(q) > int(max_items):
                q = q[-int(max_items):]
        except Exception:
            # if queue got weird, reset it
            q = [payload]
        self._save_queue(q)

    # ----------------------------
    # HTTP Send (LOW MEM)
    # ----------------------------
    def _post(self, payload, timeout_s=8):
        if not requests:
            return False, "no_urequests"

        if not self.device_id or not self.device_key:
            return False, "missing_device_auth"

        headers = {
            "Content-Type": "application/json",
            "X-Device-Id": self.device_id,
            "X-Device-Key": self.device_key,
        }

        # Clean up before network work
        _gc_collect()

        j = _json()

        try:
            # Build request body (this is the big allocation — keep payload compact!)
            body = j.dumps(payload)

            # Some urequests builds don't support timeout kwarg
            try:
                r = requests.post(self.endpoint, data=body, headers=headers, timeout=int(timeout_s))
            except TypeError:
                r = requests.post(self.endpoint, data=body, headers=headers)

            # Free the big string ASAP
            try:
                del body
            except Exception:
                pass

            status = getattr(r, "status_code", None)

            # CRITICAL: do not read r.text / r.json()
            try:
                r.close()
            except Exception:
                pass

            try:
                del r
            except Exception:
                pass

            _gc_collect()

            if status is None:
                return False, "no_status"

            if 200 <= int(status) < 300:
                return True, "OK"

            return False, "HTTP {}".format(status)

        except MemoryError:
            _gc_collect()
            return False, "ENOMEM"

        except OSError as e:
            _gc_collect()
            # OSError(12) == ENOMEM (common)
            try:
                code = e.args[0]
            except Exception:
                code = "?"
            return False, "EXC OSError({})".format(code)

        except Exception as e:
            _gc_collect()
            return False, "EXC {}".format(repr(e))

    # ----------------------------
    # Public Send
    # ----------------------------
    def send(self, payload, retries=3):
        backoff = 1
        last_msg = ""

        # keep retries small; each retry allocates JSON again
        try:
            retries = int(retries)
        except Exception:
            retries = 3
        if retries < 1:
            retries = 1
        if retries > 3:
            retries = 3

        for _ in range(retries):
            ok, msg = self._post(payload)
            last_msg = msg
            self._last_error = msg

            if ok:
                # Only try a light flush. If anything fails, stop.
                self.flush_queue(max_to_try=8)
                return True, "sent"

            time.sleep(backoff)
            backoff *= 2

        # Queue on repeated failure
        self._enqueue(payload)
        return False, "queued: {}".format(last_msg)

    def flush_queue(self, max_to_try=10):
        """
        Flush a limited number of queued items.
        Stops on first failure to avoid long loops + repeated allocations when offline.
        """
        q = self._load_queue()
        if not q:
            return

        try:
            max_to_try = int(max_to_try)
        except Exception:
            max_to_try = 10
        if max_to_try < 1:
            max_to_try = 1

        new_q = []
        tried = 0

        for item in q:
            if tried >= max_to_try:
                # keep the rest
                new_q.append(item)
                continue

            tried += 1
            ok, msg = self._post(item)
            if not ok:
                # keep this item and the rest; stop early
                new_q.append(item)
                self._last_error = msg
                # append remaining untried items
                # (avoids more _post calls)
                idx = tried  # number tried so far
                # since we can't easily resume iteration index in MicroPython,
                # we just break and keep the rest by slicing q.
                break

        # If we broke early, preserve remaining items
        if tried < len(q):
            # We attempted 'tried' items; keep the remainder
            try:
                remaining = q[tried:]
                for it in remaining:
                    if it not in new_q:
                        new_q.append(it)
            except Exception:
                pass

        self._save_queue(new_q)
