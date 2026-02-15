# src/net/telemetry_client.py

import time
import json

try:
    import urequests as requests
except ImportError:
    requests = None

QUEUE_FILE = "telemetry_queue.json"


class TelemetryClient:

    def __init__(self, api_base, device_id, device_key):
        self.api_base = api_base.rstrip("/")
        self.endpoint = self.api_base + "/api/v1/telemetry"
        self.device_id = device_id
        self.device_key = device_key

    # ----------------------------
    # Queue Handling
    # ----------------------------
    def _load_queue(self):
        try:
            with open(QUEUE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_queue(self, q):
        with open(QUEUE_FILE, "w") as f:
            json.dump(q, f)

    def _enqueue(self, payload):
        q = self._load_queue()
        q.append(payload)
        self._save_queue(q)

    # ----------------------------
    # HTTP Send
    # ----------------------------
    def _post(self, payload, timeout=8):
        if not requests:
            return False, "no urequests"

        headers = {
            "Content-Type": "application/json",
            "X-Device-Id": self.device_id,
            "X-Device-Key": self.device_key
        }

        try:
            r = requests.post(
                self.endpoint,
                json=payload,
                headers=headers
            )
            status = r.status_code
            r.close()

            if 200 <= status < 300:
                return True, "OK"
            return False, "HTTP {}".format(status)

        except Exception as e:
            return False, repr(e)

    # ----------------------------
    # Public Send
    # ----------------------------
    def send(self, payload, retries=3):
        """
        Sends telemetry.
        Retries with backoff.
        On failure → queue.
        On success → flush queue.
        """

        backoff = 1

        for attempt in range(retries):
            ok, msg = self._post(payload)

            if ok:
                self.flush_queue()
                return True, "sent"

            time.sleep(backoff)
            backoff *= 2

        # Failed → queue
        self._enqueue(payload)
        return False, "queued"

    def flush_queue(self):
        q = self._load_queue()
        if not q:
            return

        new_q = []

        for item in q:
            ok, msg = self._post(item)
            if not ok:
                new_q.append(item)

        self._save_queue(new_q)
