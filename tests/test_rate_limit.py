from backend.rate_limit import check_rate_limit


def test_allows_up_to_the_limit():
    key = "test:allow"
    for _ in range(5):
        assert check_rate_limit(key, limit=5, window_seconds=60) is True


def test_refuses_once_over_the_limit():
    key = "test:refuse"
    for _ in range(3):
        check_rate_limit(key, limit=3, window_seconds=60)
    assert check_rate_limit(key, limit=3, window_seconds=60) is False


def test_refused_attempt_is_not_itself_recorded():
    # A 429 shouldn't extend the window or eat into the caller's future
    # budget once it legitimately clears -- only genuine attempts count.
    key = "test:not-recorded"
    for _ in range(2):
        check_rate_limit(key, limit=2, window_seconds=60)
    for _ in range(5):
        assert check_rate_limit(key, limit=2, window_seconds=60) is False
    # Still exactly at the original limit, not further depleted.
    assert check_rate_limit(key, limit=3, window_seconds=60) is True


def test_window_expiry_allows_new_attempts(monkeypatch):
    import backend.rate_limit as rate_limit_module

    fake_now = [1000.0]
    monkeypatch.setattr(rate_limit_module.time, "monotonic", lambda: fake_now[0])

    key = "test:expiry"
    for _ in range(2):
        assert check_rate_limit(key, limit=2, window_seconds=10) is True
    assert check_rate_limit(key, limit=2, window_seconds=10) is False

    fake_now[0] += 11  # past the 10-second window
    assert check_rate_limit(key, limit=2, window_seconds=10) is True


def test_different_keys_are_independent():
    assert check_rate_limit("test:a", limit=1, window_seconds=60) is True
    assert check_rate_limit("test:b", limit=1, window_seconds=60) is True
    # "a" is now at its limit, but that must not affect "b" or a fresh key.
    assert check_rate_limit("test:a", limit=1, window_seconds=60) is False
    assert check_rate_limit("test:c", limit=1, window_seconds=60) is True
