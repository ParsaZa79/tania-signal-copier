import json

from src import broker_catalog


def _isolate_catalog(monkeypatch, tmp_path):
    catalog_path = tmp_path / "broker_servers.json"
    monkeypatch.setattr(broker_catalog, "BROKER_CATALOG_PATH", catalog_path)
    return catalog_path


def test_list_broker_servers_includes_seed_catalog(monkeypatch, tmp_path):
    _isolate_catalog(monkeypatch, tmp_path)

    brokers = broker_catalog.list_broker_servers()

    amarkets = next(item for item in brokers if item["value"] == "AMarkets-Real")
    assert amarkets["label"] == "AMarkets - Real (AMarkets-Real)"
    assert amarkets["source"] == "seed"


def test_paginate_broker_servers_keeps_brand_servers_together(monkeypatch, tmp_path):
    _isolate_catalog(monkeypatch, tmp_path)
    brokers = broker_catalog.list_broker_servers()

    first_page, total = broker_catalog.paginate_broker_servers(
        brokers,
        page=1,
        page_size=1,
    )

    assert total == 24
    assert [item["value"] for item in first_page] == ["AMarkets-Real", "AMarkets-Demo"]


def test_paginate_broker_servers_searches_the_full_catalog(monkeypatch, tmp_path):
    _isolate_catalog(monkeypatch, tmp_path)
    brokers = broker_catalog.list_broker_servers()

    results, total = broker_catalog.paginate_broker_servers(
        brokers,
        page=1,
        page_size=8,
        query="Axiory-Demo",
    )

    assert total == 1
    assert [item["value"] for item in results] == ["Axiory-Live", "Axiory-Demo"]


def test_record_broker_server_persists_successful_unknown_server(monkeypatch, tmp_path):
    catalog_path = _isolate_catalog(monkeypatch, tmp_path)

    broker_catalog.record_broker_server("NewBroker-Live", "New Broker Ltd")
    broker_catalog.record_broker_server("NewBroker-Live", "New Broker Ltd")

    stored = json.loads(catalog_path.read_text(encoding="utf-8"))
    assert stored["servers"]["NewBroker-Live"]["label"] == "New Broker Ltd (NewBroker-Live)"
    assert stored["servers"]["NewBroker-Live"]["company"] == "New Broker Ltd"
    assert stored["servers"]["NewBroker-Live"]["success_count"] == 2

    learned = next(
        item for item in broker_catalog.list_broker_servers() if item["value"] == "NewBroker-Live"
    )
    assert learned["label"] == "New Broker Ltd (NewBroker-Live)"
    assert learned["source"] == "learned"


def test_record_broker_server_does_not_duplicate_seed_entries(monkeypatch, tmp_path):
    catalog_path = _isolate_catalog(monkeypatch, tmp_path)

    broker_catalog.record_broker_server("AMarkets-Real", "AMarkets")

    assert not catalog_path.exists()
    brokers = [
        item for item in broker_catalog.list_broker_servers() if item["value"] == "AMarkets-Real"
    ]
    assert brokers == [
        {
            "value": "AMarkets-Real",
            "label": "AMarkets - Real (AMarkets-Real)",
            "source": "seed",
        }
    ]
