from psycopg.errors import OperationalError, UniqueViolation
from psycopg_pool import PoolTimeout

from src import database


def test_is_connection_error_true_for_pool_timeout():
    # The actual "couldn't get a connection after 30.00 sec" exception
    # (psycopg_pool.PoolTimeout) is a subclass of OperationalError -- this
    # is what the ingestion scripts' backoff logic keys off of.
    assert database.is_connection_error(PoolTimeout("couldn't get a connection after 30.00 sec")) is True


def test_is_connection_error_true_for_plain_operational_error():
    assert database.is_connection_error(OperationalError("server closed the connection unexpectedly")) is True


def test_is_connection_error_false_for_a_data_error():
    # A bad record (e.g. a duplicate key) isn't a reason to back off --
    # it's isolated and unrelated to whether the database is reachable.
    assert database.is_connection_error(UniqueViolation("duplicate key value")) is False


def test_is_connection_error_false_for_an_unrelated_exception():
    assert database.is_connection_error(ValueError("bad input")) is False


def test_backoff_sleep_delay_grows_with_attempt_and_is_capped(monkeypatch):
    delays = []
    monkeypatch.setattr(database.time, "sleep", lambda seconds: delays.append(seconds))
    monkeypatch.setattr(database.random, "uniform", lambda a, b: 0)

    database.backoff_sleep(1, base=2, cap=60)
    database.backoff_sleep(2, base=2, cap=60)
    database.backoff_sleep(3, base=2, cap=60)
    database.backoff_sleep(10, base=2, cap=60)

    assert delays == [2, 4, 8, 60]


def test_backoff_sleep_adds_jitter(monkeypatch):
    monkeypatch.setattr(database.time, "sleep", lambda seconds: recorded.append(seconds))
    monkeypatch.setattr(database.random, "uniform", lambda a, b: 0.5)
    recorded = []

    database.backoff_sleep(1, base=2, cap=60)

    assert recorded == [2.5]
