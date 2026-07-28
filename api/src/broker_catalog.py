"""MT5 broker server catalog with learn-on-success persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .runtime_data import DATA_DIR

BROKER_CATALOG_PATH = DATA_DIR / "broker_servers.json"

BROKER_BRAND_PREFIXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AMarkets", ("AMarkets-",)),
    ("Admirals", ("AdmiralMarkets-",)),
    ("Exness", ("Exness-",)),
    ("IC Markets", ("ICMarketsSC-",)),
    ("Pepperstone", ("Pepperstone-",)),
    ("OANDA", ("OANDA-",)),
    ("Eightcap", ("Eightcap-",)),
    ("FP Markets", ("FPMarkets-",)),
    ("Axiory", ("Axiory-",)),
    ("BlackBull Markets", ("BlackBullMarkets-",)),
    ("Blueberry Markets", ("BlueberryMarkets-",)),
    ("FBS", ("FBS-",)),
    ("Fusion Markets", ("FusionMarkets-",)),
    ("FxPro", ("FxPro",)),
    ("HFM", ("HFM-",)),
    ("IronFX", ("IronFX-",)),
    ("JustMarkets", ("JustMarkets-",)),
    ("LiteFinance", ("LiteFinance-",)),
    ("MetaQuotes", ("MetaQuotes-",)),
    ("Octa", ("OctaFX-",)),
    ("RoboForex", ("RoboForex-",)),
    ("Tickmill", ("Tickmill-",)),
    ("Vantage", ("VantageInternational-",)),
    ("XM", ("XMGlobal-",)),
)

SEED_MT5_BROKER_SERVERS: list[dict[str, str]] = [
    {"value": "AMarkets-Real", "label": "AMarkets - Real (AMarkets-Real)"},
    {"value": "AMarkets-Demo", "label": "AMarkets - Demo (AMarkets-Demo)"},
    {"value": "AdmiralMarkets-Live", "label": "Admirals - Live (AdmiralMarkets-Live)"},
    {"value": "AdmiralMarkets-Demo", "label": "Admirals - Demo (AdmiralMarkets-Demo)"},
    {"value": "Axiory-Live", "label": "Axiory - Live (Axiory-Live)"},
    {"value": "Axiory-Demo", "label": "Axiory - Demo (Axiory-Demo)"},
    {"value": "BlackBullMarkets-Live", "label": "BlackBull Markets - Live (BlackBullMarkets-Live)"},
    {"value": "BlackBullMarkets-Demo", "label": "BlackBull Markets - Demo (BlackBullMarkets-Demo)"},
    {"value": "BlueberryMarkets-Live", "label": "Blueberry Markets - Live (BlueberryMarkets-Live)"},
    {"value": "BlueberryMarkets-Demo", "label": "Blueberry Markets - Demo (BlueberryMarkets-Demo)"},
    {"value": "Eightcap-Real", "label": "Eightcap - Real (Eightcap-Real)"},
    {"value": "Eightcap-Demo", "label": "Eightcap - Demo (Eightcap-Demo)"},
    {"value": "Exness-MT5Real", "label": "Exness - Real (Exness-MT5Real)"},
    {"value": "Exness-MT5Real2", "label": "Exness - Real 2 (Exness-MT5Real2)"},
    {"value": "Exness-MT5Real3", "label": "Exness - Real 3 (Exness-MT5Real3)"},
    {"value": "Exness-MT5Trial", "label": "Exness - Demo (Exness-MT5Trial)"},
    {"value": "FBS-Real", "label": "FBS - Real (FBS-Real)"},
    {"value": "FBS-Demo", "label": "FBS - Demo (FBS-Demo)"},
    {"value": "FPMarkets-Live", "label": "FP Markets - Live (FPMarkets-Live)"},
    {"value": "FPMarkets-Demo", "label": "FP Markets - Demo (FPMarkets-Demo)"},
    {"value": "FusionMarkets-Live", "label": "Fusion Markets - Live (FusionMarkets-Live)"},
    {"value": "FusionMarkets-Demo", "label": "Fusion Markets - Demo (FusionMarkets-Demo)"},
    {"value": "FxPro-MT5", "label": "FxPro - MT5 (FxPro-MT5)"},
    {"value": "FxPro.com-Real", "label": "FxPro - Real (FxPro.com-Real)"},
    {"value": "FxPro.com-Demo", "label": "FxPro - Demo (FxPro.com-Demo)"},
    {"value": "HFM-Live", "label": "HFM - Live (HFM-Live)"},
    {"value": "HFM-Demo", "label": "HFM - Demo (HFM-Demo)"},
    {"value": "ICMarketsSC-MT5", "label": "IC Markets - MT5 (ICMarketsSC-MT5)"},
    {"value": "ICMarketsSC-MT5-2", "label": "IC Markets - MT5 2 (ICMarketsSC-MT5-2)"},
    {"value": "ICMarketsSC-Demo", "label": "IC Markets - Demo (ICMarketsSC-Demo)"},
    {"value": "IronFX-Live", "label": "IronFX - Live (IronFX-Live)"},
    {"value": "IronFX-Demo", "label": "IronFX - Demo (IronFX-Demo)"},
    {"value": "JustMarkets-Live", "label": "JustMarkets - Live (JustMarkets-Live)"},
    {"value": "JustMarkets-Demo", "label": "JustMarkets - Demo (JustMarkets-Demo)"},
    {"value": "LiteFinance-ECN", "label": "LiteFinance - ECN (LiteFinance-ECN)"},
    {"value": "LiteFinance-Demo", "label": "LiteFinance - Demo (LiteFinance-Demo)"},
    {"value": "MetaQuotes-Demo", "label": "MetaQuotes - Demo (MetaQuotes-Demo)"},
    {"value": "OANDA-v20 Live-1", "label": "OANDA - Live (OANDA-v20 Live-1)"},
    {"value": "OANDA-v20 Practice-1", "label": "OANDA - Practice (OANDA-v20 Practice-1)"},
    {"value": "OctaFX-Real", "label": "Octa - Real (OctaFX-Real)"},
    {"value": "OctaFX-Demo", "label": "Octa - Demo (OctaFX-Demo)"},
    {"value": "Pepperstone-MT5-Live01", "label": "Pepperstone - Live 01 (Pepperstone-MT5-Live01)"},
    {"value": "Pepperstone-MT5-Live02", "label": "Pepperstone - Live 02 (Pepperstone-MT5-Live02)"},
    {"value": "Pepperstone-Demo", "label": "Pepperstone - Demo (Pepperstone-Demo)"},
    {"value": "RoboForex-ECN", "label": "RoboForex - ECN (RoboForex-ECN)"},
    {"value": "RoboForex-Pro", "label": "RoboForex - Pro (RoboForex-Pro)"},
    {"value": "RoboForex-Demo", "label": "RoboForex - Demo (RoboForex-Demo)"},
    {"value": "Tickmill-Live", "label": "Tickmill - Live (Tickmill-Live)"},
    {"value": "Tickmill-Demo", "label": "Tickmill - Demo (Tickmill-Demo)"},
    {"value": "VantageInternational-Live", "label": "Vantage - Live (VantageInternational-Live)"},
    {"value": "VantageInternational-Demo", "label": "Vantage - Demo (VantageInternational-Demo)"},
    {"value": "XMGlobal-MT5", "label": "XM - MT5 (XMGlobal-MT5)"},
    {"value": "XMGlobal-Demo", "label": "XM - Demo (XMGlobal-Demo)"},
]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _clean_server(server: str | None) -> str:
    return "".join(ch for ch in (server or "").strip() if ch.isprintable())[:120]


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return data if isinstance(data, dict) else default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _seed_values() -> set[str]:
    return {item["value"] for item in SEED_MT5_BROKER_SERVERS}


def _learned_label(server: str, company: str | None = None) -> str:
    clean_company = (company or "").strip()
    if clean_company and clean_company.lower() not in server.lower():
        return f"{clean_company} ({server})"
    return server


def list_broker_servers() -> list[dict[str, str]]:
    """Return seed broker servers plus learned successful servers."""
    options = [{**item, "source": "seed"} for item in SEED_MT5_BROKER_SERVERS]
    seen = _seed_values()
    store = _read_json(BROKER_CATALOG_PATH, {"servers": {}})
    servers = store.get("servers", {})
    if isinstance(servers, dict):
        learned = []
        for server, payload in servers.items():
            value = _clean_server(str(server))
            if not value or value in seen:
                continue
            label = value
            if isinstance(payload, dict):
                label = str(payload.get("label") or value)
            learned.append({"value": value, "label": label, "source": "learned"})
            seen.add(value)
        options.extend(sorted(learned, key=lambda item: item["label"].lower()))
    return options


def paginate_broker_servers(
    options: list[dict[str, str]],
    *,
    page: int,
    page_size: int,
    query: str = "",
) -> tuple[list[dict[str, str]], int]:
    """Return one page of server options, grouped and counted by broker brand."""
    normalized_query = query.strip().casefold()
    groups: list[list[dict[str, str]]] = []

    for brand_name, prefixes in BROKER_BRAND_PREFIXES:
        servers = [
            option
            for option in options
            if any(option["value"].startswith(prefix) for prefix in prefixes)
        ]
        if not servers:
            continue
        if normalized_query and not (
            normalized_query in brand_name.casefold()
            or any(
                normalized_query in option["label"].casefold()
                or normalized_query in option["value"].casefold()
                for option in servers
            )
        ):
            continue
        groups.append(servers)

    total = len(groups)
    start = (page - 1) * page_size
    selected_groups = groups[start : start + page_size]
    return [option for group in selected_groups for option in group], total


def record_broker_server(server: str | None, company: str | None = None) -> None:
    """Record a server after a successful MT5 login so future users can select it."""
    value = _clean_server(server)
    if not value or value in _seed_values():
        return

    store = _read_json(BROKER_CATALOG_PATH, {"servers": {}})
    servers = store.setdefault("servers", {})
    if not isinstance(servers, dict):
        servers = {}
        store["servers"] = servers

    now = _utc_now()
    payload = servers.get(value)
    if not isinstance(payload, dict):
        payload = {"first_seen_at": now, "success_count": 0}

    payload["label"] = _learned_label(value, company)
    payload["company"] = (company or "").strip()
    payload["last_seen_at"] = now
    payload["success_count"] = int(payload.get("success_count") or 0) + 1
    servers[value] = payload
    _write_json(BROKER_CATALOG_PATH, store)
