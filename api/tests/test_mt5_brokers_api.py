from __future__ import annotations

from fastapi.testclient import TestClient

from src import security
from src.main import app
from src.routers import mt5


def test_mt5_brokers_endpoint_validates_and_serializes_catalog(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("WORKOS_CLIENT_ID", raising=False)
    monkeypatch.setattr(security, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(security, "DEV_SECRET_PATH", tmp_path / ".dev_app_secret")
    user = security.create_user("owner@example.com", "correct horse battery")
    token = security.create_token(user["id"])
    monkeypatch.setattr(
        mt5,
        "list_broker_servers",
        lambda: [
            {"value": "AMarkets-Real", "label": "AMarkets Real"},
            {
                "value": "AMarkets-Custom",
                "label": "AMarkets Learned",
                "source": "learned",
            },
            {"value": "Axiory-Live", "label": "Axiory Live"},
        ],
    )

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as client:
        response = client.get("/api/mt5/brokers?page=1&page_size=1&query=amarkets")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "brokers": [
            {"value": "AMarkets-Real", "label": "AMarkets Real", "source": "seed"},
            {
                "value": "AMarkets-Custom",
                "label": "AMarkets Learned",
                "source": "learned",
            },
        ],
        "page": 1,
        "page_size": 1,
        "total": 1,
        "total_pages": 1,
    }
