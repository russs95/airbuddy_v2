# src/net/telemetry_client.py  (LOW-MEM, Pico-friendly)
#
# Updated:
# - Reads tiny JSON response on success to extract server_now (unix seconds)
# - Prints:
#     True Sent
#     Device Time : dd/mm/yy hh:mm:ss
#     Server Time : dd/mm/yy hh:mm:ss
#     Clock Drift : N seconds
#     #########################################

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

    # --------------------------------------------------
    # Timestamp Formatter (Human Readable)
    # --------------------------------------------------
    def _fmt_epoch(self, epoch_s):
        try:
            t = time.localtime(int(epoch_s))
            return "%02d/%02d/%02d %02d:%02d:%02d" % (
                t[2], t[1], t[0] % 100,
                t[3], t[4], t[5]
            )
        except Exception:
            return str(epoch_s)

    def _payload_ts(self, payload):
        """Extract device timestamp (unix seconds) from payload."""
        try:
            if isinstance(payload, dict):
                ts = payload.get("recorded_at", None)
                if ts is None:
                    ts = payload.get("ts", None)
                return ts
        except Exception:
            pass
        return None

    def _print_send_stamp(self, payload, server_now=None, prefix="True Sent"):
        """Print human readable device/server time + drift + separator."""
        try:
            ts = self._payload_ts(payload)

            print(prefix)

            if ts:
                print("Device Time :", self._fmt_epoch(ts))

            if server_now:
                print("Server Time :", self._fmt_epoch(server_now))
                if ts:
                    try:
                        drift = int(server_now) - int(ts)
                        print("Clock Drift :", drift, "seconds")
                    except Exception:
                        pass

            print("#########################################")
        except Exception:
            pass

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
            q = [payload]
        self._save_queue(q)

    # ----------------------------
    # HTTP Send (LOW MEM)
    # ----------------------------
    def _post(self, payload, timeout_s=8):
        """
        Returns:
          (ok: bool, msg: str, server_now: int|None)
        """
        if not requests:
            return False, "no_urequests", None

        if not self.device_id or not self.device_key:
            return False, "missing_device_auth", None

        headers = {
            "Content-Type": "application/json",
            "X-Device-Id": self.device_id,
            "X-Device-Key": self.device_key,
        }

        _gc_collect()
        j = _json()

        try:
            # Big allocation: JSON body string (keep payload compact)
            body = j.dumps(payload)

            try:
                r = requests.post(self.endpoint, data=body, headers=headers, timeout=int(timeout_s))
            except TypeError:
                r = requests.post(self.endpoint, data=body, headers=headers)

            # free big string ASAP
            try:
                del body
            except Exception:
                pass

            status = getattr(r, "status_code", None)
            server_now = None

            # On success, try to read the small JSON response: { ok:true, server_now:<unix> }
            if status is not None and 200 <= int(status) < 300:
                try:
                    data = r.json()
                    if isinstance(data, dict):
                        server_now = data.get("server_now", None)
                except Exception:
                    pass

            # Always close response
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
                return False, "no_status", None

            if 200 <= int(status) < 300:
                return True, "OK", server_now

            return False, "HTTP {}".format(status), None

        except MemoryError:
            _gc_collect()
            return False, "ENOMEM", None

        except OSError as e:
            _gc_collect()
            try:
                code = e.args[0]
            except Exception:
                code = "?"
            return False, "EXC OSError({})".format(code), None

        except Exception as e:
            _gc_collect()
            return False, "EXC {}".format(repr(e)), None

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
            ok, msg, server_now = self._post(payload)
            last_msg = msg
            self._last_error = msg

            if ok:
                # Print stamp UNDER "True Sent" with server drift
                self._print_send_stamp(payload, server_now=server_now, prefix="True Sent")

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
            ok, msg, server_now = self._post(item)
            if not ok:
                # keep this item and the rest; stop early
                new_q.append(item)
                self._last_error = msg
                break
            else:
                # Print flush success stamp too (helps see backlog clearing)
                self._print_send_stamp(item, server_now=server_now, prefix="True Sent (flush)")

        # Preserve any remaining items after the break
        if tried < len(q):
            try:
                remaining = q[tried:]
                for it in remaining:
                    if it not in new_q:
                        new_q.append(it)
            except Exception:
                pass

        self._save_queue(new_q)