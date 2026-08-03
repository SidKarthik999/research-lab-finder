"""Shared ORCID public API client: OAuth client-credentials token, request
throttling/retry, and the GET helper. Used by enrich_names.py and
researcher_urls.py so the auth/throttle logic lives in exactly one place.
"""

import os
import threading
import time

import requests
from dotenv import load_dotenv

load_dotenv()

ORCID_API_BASE = "https://pub.orcid.org/v3.0"
ORCID_TOKEN_URL = "https://orcid.org/oauth/token"
ORCID_CLIENT_ID = os.getenv("ORCID_CLIENT_ID")
ORCID_CLIENT_SECRET = os.getenv("ORCID_CLIENT_SECRET")
USER_AGENT = "researchlabfinder-bot (contact: sanjanakarthik789@gmail.com)"

_orcid_token_lock = threading.Lock()
_orcid_token = [None]


def _get_orcid_token():
    if not ORCID_CLIENT_ID or not ORCID_CLIENT_SECRET:
        return None

    with _orcid_token_lock:
        if _orcid_token[0] is None:
            response = requests.post(
                ORCID_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": ORCID_CLIENT_ID,
                    "client_secret": ORCID_CLIENT_SECRET,
                    "grant_type": "client_credentials",
                    "scope": "/read-public",
                },
                timeout=10,
            )
            response.raise_for_status()
            _orcid_token[0] = response.json()["access_token"]
        return _orcid_token[0]


ORCID_MIN_INTERVAL = 0.1 if (ORCID_CLIENT_ID and ORCID_CLIENT_SECRET) else 1.0
ORCID_MAX_RETRIES = 3
_orcid_lock = threading.Lock()
_orcid_next_allowed_at = [0.0]


def _throttle_orcid():
    with _orcid_lock:
        now = time.monotonic()
        wait_seconds = _orcid_next_allowed_at[0] - now
        if wait_seconds > 0:
            time.sleep(wait_seconds)
            now = time.monotonic()
        _orcid_next_allowed_at[0] = now + ORCID_MIN_INTERVAL


def normalize_orcid(orcid):
    return orcid.rstrip("/").rsplit("/", 1)[-1]


def get_orcid(path):
    url = f"{ORCID_API_BASE}/{path}"
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}

    token = _get_orcid_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(ORCID_MAX_RETRIES):
        _throttle_orcid()
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else 10 * (attempt + 1)
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        return response.json()

    response.raise_for_status()
