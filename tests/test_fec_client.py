"""Offline tests for FECClient pagination and error handling (no network)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import fec_client
from src.fec_client import FECAPIError, FECClient, FECRateLimitError

fec_client.time.sleep = lambda *_: None  # no waiting in tests


def make_client():
    return FECClient(api_key="test-key")


# ---- Schedule B follows the cursor ----
RECORDS = [{"sub_id": str(i)} for i in range(250)]


def cursor_api(path, params):
    start = int(params.get("last_index", 0))
    chunk = RECORDS[start:start + 100]
    nxt = start + 100
    cursor = {"last_index": str(nxt)} if nxt < len(RECORDS) else None
    return {"results": chunk, "pagination": {"count": 250, "last_indexes": cursor}}


c = make_client()
c._get = cursor_api
got = c.get_disbursements("C1", 2024)
assert len(got) == 250 and len({r["sub_id"] for r in got}) == 250, len(got)


# ---- An API that ignores the cursor must not loop forever or duplicate ----
def stuck_api(path, params):
    return {"results": RECORDS[:100], "pagination": {"last_indexes": {"last_index": "x"}}}


c = make_client()
c._get = stuck_api
got = c.get_disbursements("C1", 2024)
assert len(got) == 100, len(got)


# ---- Error handling ----
class Resp:
    def __init__(self, status):
        self.status_code, self.text = status, "x"

    def json(self):
        return {}


def client_with_status(status):
    c = make_client()
    calls = []
    c._session.get = lambda *a, **k: (calls.append(1), Resp(status))[1]
    return c, calls


c, calls = client_with_status(429)
try:
    c._get("/x", {})
    raise AssertionError("expected FECRateLimitError")
except FECRateLimitError:
    assert len(calls) == c.max_retries

c, calls = client_with_status(403)  # invalid key: fail at once
try:
    c._get("/x", {})
    raise AssertionError("expected FECAPIError")
except FECAPIError as e:
    assert not isinstance(e, FECRateLimitError) and len(calls) == 1

c, calls = client_with_status(503)  # server trouble: retry
try:
    c._get("/x", {})
    raise AssertionError("expected FECAPIError")
except FECAPIError:
    assert len(calls) == c.max_retries

print("fec_client tests passed")
