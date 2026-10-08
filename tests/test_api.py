import json

from tests.conftest import make_client

ORDER = {"asset": "eurusd", "direction": "call", "amount": 1, "expiration_minutes": 1}


def test_requires_api_key(client):
    assert client.get("/api/v1/session/status").status_code == 401
    assert client.get("/api/v1/session/status", headers={"X-API-Key": "bad"}).status_code == 401


def test_liveness_is_public(client):
    assert client.get("/health/live").json() == {"status": "alive"}


def test_readiness_reflects_broker_connection(client, headers):
    assert client.get("/health/ready").status_code == 503
    client.post("/api/v1/session/connect", headers=headers)
    assert client.get("/health/ready").status_code == 200


def test_full_flow(client, headers):
    client.post("/api/v1/session/connect", headers=headers)
    assert client.get("/api/v1/account/balance", headers=headers).json()["amount"] == 1000.0

    r = client.post("/api/v1/trading/orders", json=ORDER, headers=headers)
    assert r.status_code == 201
    assert r.json()["asset"] == "EURUSD"
    oid = r.json()["order_id"]

    res = client.get(f"/api/v1/trading/orders/{oid}/result", headers=headers).json()
    assert res["outcome"] == "win"


def test_candles_validation(client, headers):
    client.post("/api/v1/session/connect", headers=headers)
    ok = client.get("/api/v1/market/candles?asset=EURUSD&interval=60&count=3", headers=headers)
    assert ok.status_code == 200 and len(ok.json()) == 3
    bad = client.get("/api/v1/market/candles?asset=EURUSD&interval=7&count=3", headers=headers)
    assert bad.status_code == 400


def test_trading_disabled_blocks_orders(tmp_path):
    c, gw = make_client(tmp_path, trading_enabled=False)
    with c:
        c.post("/api/v1/session/connect", headers={"X-API-Key": "secret-key"})
        r = c.post("/api/v1/trading/orders", json=ORDER, headers={"X-API-Key": "secret-key"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "trading_disabled"
    assert gw.orders == []


def test_max_amount_enforced(tmp_path):
    c, gw = make_client(tmp_path, max_amount=5)
    with c:
        h = {"X-API-Key": "secret-key"}
        c.post("/api/v1/session/connect", headers=h)
        r = c.post("/api/v1/trading/orders", json={**ORDER, "amount": 50}, headers=h)
    assert r.status_code == 403 and gw.orders == []


def test_real_account_switch_denied(client, headers):
    client.post("/api/v1/session/connect", headers=headers)
    r = client.post("/api/v1/account/switch", json={"account_type": "REAL"}, headers=headers)
    assert r.status_code == 403


def test_audit_trail_written_with_client_and_no_secrets(tmp_path):
    c, _ = make_client(tmp_path)
    with c:
        h = {"X-API-Key": "secret-key"}
        c.post("/api/v1/session/connect", headers=h)
        c.post("/api/v1/trading/orders", json=ORDER, headers=h)
    lines = [json.loads(x) for x in (tmp_path / "logs" / "audit.log").read_text().splitlines()]
    actions = [(l["action"], l["outcome"]) for l in lines]
    assert ("trading.order.requested", "received") in actions
    assert ("trading.order.placed", "success") in actions
    assert all(l["client_id"] in ("tester", "-", "system") for l in lines)
    assert "secret-key" not in (tmp_path / "logs" / "audit.log").read_text()
