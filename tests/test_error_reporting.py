from backend.error_reporting import scrub_event


def test_scrub_event_filters_authorization_and_cookie_headers():
    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer secret-token",
                "Cookie": "session=abc123",
                "User-Agent": "pytest",
            }
        }
    }
    scrubbed = scrub_event(event, {})
    assert scrubbed["request"]["headers"]["Authorization"] == "[Filtered]"
    assert scrubbed["request"]["headers"]["Cookie"] == "[Filtered]"
    assert scrubbed["request"]["headers"]["User-Agent"] == "pytest"


def test_scrub_event_is_case_insensitive_on_header_names():
    event = {"request": {"headers": {"authorization": "Bearer x", "cookie": "y"}}}
    scrubbed = scrub_event(event, {})
    assert scrubbed["request"]["headers"]["authorization"] == "[Filtered]"
    assert scrubbed["request"]["headers"]["cookie"] == "[Filtered]"


def test_scrub_event_handles_no_request_context():
    event = {"message": "boom"}
    assert scrub_event(event, {}) == {"message": "boom"}


def test_scrub_event_handles_request_with_no_headers():
    event = {"request": {"url": "https://x.test"}}
    assert scrub_event(event, {}) == {"request": {"url": "https://x.test"}}
