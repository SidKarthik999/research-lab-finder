"""Shared OpenAlex request hardening: pyalex config (api key, polite-pool
email, bounded retries) and a patched requests session (real timeout, no
unbounded Retry-After sleeps, inter-request pacing). Imported for its
side effects by openalex.py, publications.py, and topics.py so every
OpenAlex-hitting script gets the same protection -- this used to be
duplicated only in openalex.py until publications.py/topics.py needed the
same thing (mirrors why orcid_client.py exists for the ORCID side).

Three problems found the hard way debugging a run that appeared to "hang"
with 0% CPU for 6-40+ minutes at a time, no output, no exception:

1. pyalex's session.get() calls never pass a `timeout` kwarg (checked its
   source directly), and requests/urllib3 treat "no timeout given" as
   "block forever" -- this is NOT the same as inheriting a process-wide
   socket.setdefaulttimeout(), which urllib3 explicitly overrides with its
   own timeout=None when none is passed. socket.setdefaulttimeout() was
   tried first and confirmed to have NO effect, hence the explicit
   Session.request patch below.
2. urllib3's Retry, by default, respects a 429 response's `Retry-After`
   header and sleeps for exactly that long between retries -- which, once
   OpenAlex is genuinely rate-limiting a client hard (confirmed live: a
   request against this exact query returned 429 immediately after an
   earlier run's ~40k-request burst), can mean multi-minute blocking
   sleeps per retry, invisible to any request-level timeout since the
   sleep happens in urllib3's retry loop, not during the request itself.
   respect_retry_after_header=False forces our own bounded backoff_factor
   schedule instead.
3. No pacing between requests at all -- back-to-back requests are exactly
   the burst pattern that tripped sustained 429s in the first place.
   _throttle_openalex() mirrors orcid_client.py's min-interval pattern
   (same reasoning: cheap insurance against retriggering the same
   throttling).
"""

import os
import threading
import time

import pyalex
import pyalex.api as pyalex_api
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

pyalex.config.api_key = os.getenv("OPENALEX_API_KEY")
pyalex.config.email = os.getenv("OPENALEX_EMAIL")
pyalex.config.max_retries = 3
pyalex.config.retry_backoff_factor = 1.0
pyalex.config.retry_http_codes = [429, 500, 503]

_OPENALEX_MIN_INTERVAL = 0.2
_openalex_lock = threading.Lock()
_openalex_next_allowed_at = [0.0]


def _throttle_openalex():
    with _openalex_lock:
        now = time.monotonic()
        wait_seconds = _openalex_next_allowed_at[0] - now
        if wait_seconds > 0:
            time.sleep(wait_seconds)
            now = time.monotonic()
        _openalex_next_allowed_at[0] = now + _OPENALEX_MIN_INTERVAL


def _get_requests_session_with_timeout():
    session = requests.Session()
    retries = Retry(
        total=pyalex.config.max_retries,
        backoff_factor=pyalex.config.retry_backoff_factor,
        status_forcelist=pyalex.config.retry_http_codes,
        allowed_methods={"GET", "POST"},
        respect_retry_after_header=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))

    original_request = session.request

    def _request_with_pacing(method, url, **kwargs):
        _throttle_openalex()
        kwargs.setdefault("timeout", 30)
        return original_request(method, url, **kwargs)

    session.request = _request_with_pacing
    return session


pyalex_api._get_requests_session = _get_requests_session_with_timeout
