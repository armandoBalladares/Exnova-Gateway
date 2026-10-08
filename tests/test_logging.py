import logging

from app.core.logging import JsonFormatter, redact, scrub


def test_redact_nested_secrets():
    data = {"user": "a", "password": "x", "nested": {"token": "t", "ok": 1}}
    assert redact(data) == {"user": "a", "password": "***", "nested": {"token": "***", "ok": 1}}


def test_scrub_message():
    assert "hunter2" not in scrub('login password="hunter2" ok')
    assert "abc123" not in scrub("ssid=abc123, other=1")


def test_json_formatter_includes_extras():
    rec = logging.LogRecord("t", logging.INFO, "f", 1, "hola %s", ("mundo",), None)
    rec.order_id = "1"
    rec.password = "no"
    out = JsonFormatter("svc", "dev").format(rec)
    assert '"order_id": "1"' in out and '"password": "***"' in out and "hola mundo" in out
