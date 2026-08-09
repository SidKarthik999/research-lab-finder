"""In-process rate limiting for auth endpoints (login, signup, forgot-
password) -- see docs/ROADMAP.md Phase 6.4. Guards against two things:
brute-forcing a password, and spamming a real person's inbox with signup/
reset emails by resubmitting their address repeatedly (a real nuisance
found while testing the anti-enumeration design, which deliberately never
confirms or denies whether an email has an account).

Deliberately in-memory, not Redis-backed: this app runs a single Render
instance with no horizontal scaling, so there's no state to share across
processes, and a counter reset on every process restart (Render's free
tier already restarts the container after 15 minutes idle) is a non-issue
for an abuse guard, not a security-critical control that needs to survive
a restart.

Not slowapi/limits: those key a rate limit off the raw Starlette Request,
which makes limiting by a POST body field (email) awkward -- the key
function would have to re-parse the body itself, separately from FastAPI's
own Pydantic parsing. Every route here already has the parsed body in
scope, so a small fixed-window counter keyed by whatever string the caller
passes in is simpler and just as correct for this narrow need.
"""

import threading
import time
from collections import defaultdict

_lock = threading.Lock()
_buckets = defaultdict(list)


def check_rate_limit(key, limit, window_seconds):
    """Records one attempt under `key` and returns True if it's within
    `limit` attempts per `window_seconds`, False if the caller should be
    refused. A refused attempt is not itself recorded -- it doesn't extend
    the window, only genuine attempts do."""
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        timestamps = _buckets[key]
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        return True


def reset_rate_limits():
    """Test-only: clears every counter so the shared module-level state
    doesn't leak between tests."""
    with _lock:
        _buckets.clear()
