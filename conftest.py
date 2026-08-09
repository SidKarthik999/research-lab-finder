import pytest

from backend.rate_limit import reset_rate_limits


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    # backend/rate_limit.py's counters are module-level state, shared
    # across every test in the process -- without this, whichever test
    # happens to hit an auth route enough times leaks a 429 into
    # unrelated tests that run after it.
    reset_rate_limits()
    yield
