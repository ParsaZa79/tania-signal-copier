"""MT5 connection management router."""

from contextlib import suppress
from math import ceil
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..account_store import get_active_account, load_account_config, save_account_config
from ..broker_catalog import (
    list_broker_servers,
    paginate_broker_servers,
    record_broker_server,
)
from ..dependencies import connect_account_executor

router = APIRouter()
ActiveAccount = Annotated[dict[str, Any], Depends(get_active_account)]


class MT5ConnectRequest(BaseModel):
    """Request to connect or reconnect the running API to MT5."""

    login: int | None = Field(default=None, gt=0)
    password: str | None = None
    server: str | None = None
    docker_host: str | None = None
    docker_port: int | None = Field(default=None, gt=0, le=65535)
    path: str | None = None

    @field_validator("server", "password", "docker_host", "path", mode="before")
    @classmethod
    def _strip_optional_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class MT5ConnectResponse(BaseModel):
    """Sanitized MT5 connection response."""

    success: bool
    connected: bool
    health: dict[str, Any]
    error: str | None = None


class MT5BrokerServer(BaseModel):
    value: str
    label: str
    source: str = "seed"


class MT5BrokerServersResponse(BaseModel):
    success: bool
    brokers: list[MT5BrokerServer]
    page: int
    page_size: int
    total: int
    total_pages: int


@router.get("/brokers", response_model=MT5BrokerServersResponse)
async def list_mt5_broker_servers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=8, ge=1, le=24),
    query: str = Query(default="", max_length=120),
) -> MT5BrokerServersResponse:
    """List known MT5 broker servers.

    MetaTrader does not expose broker discovery through the Python API, so this
    combines a seed catalog with servers learned from successful logins. Results
    are filtered and paginated by broker brand so a brand's servers stay together.
    """
    broker_page, total = paginate_broker_servers(
        list_broker_servers(),
        page=page,
        page_size=page_size,
        query=query,
    )
    brokers = [MT5BrokerServer.model_validate(item) for item in broker_page]
    return MT5BrokerServersResponse(
        success=True,
        brokers=brokers,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size),
    )


@router.post("/connect", response_model=MT5ConnectResponse)
async def connect_mt5(
    request: MT5ConnectRequest,
    account: ActiveAccount,
) -> MT5ConnectResponse:
    """Connect the running API process to MT5 using dashboard-provided credentials."""
    updates = {
        key: value
        for key, value in {
            "MT5_LOGIN": str(request.login) if request.login is not None else None,
            "MT5_PASSWORD": request.password,
            "MT5_SERVER": request.server,
            "MT5_DOCKER_HOST": request.docker_host,
            "MT5_DOCKER_PORT": (
                str(request.docker_port) if request.docker_port is not None else None
            ),
            "MT5_PATH": request.path,
        }.items()
        if value is not None
    }
    if updates:
        save_account_config(account["id"], updates)

    config = load_account_config(account["id"], reveal_secrets=True)
    missing = [
        label
        for label, key in (
            ("login", "MT5_LOGIN"),
            ("password", "MT5_PASSWORD"),
            ("server", "MT5_SERVER"),
        )
        if not config.get(key)
    ]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing MT5 {', '.join(missing)}")

    result = connect_account_executor(account["id"], config)
    health = result.get("health", {})
    if result.get("success") and result.get("connected"):
        with suppress(Exception):
            record_broker_server(
                str(health.get("account_server") or config.get("MT5_SERVER") or ""),
                str(health.get("account_company") or ""),
            )
    return MT5ConnectResponse(
        success=bool(result.get("success")),
        connected=bool(result.get("connected")),
        health=health,
        error=result.get("error"),
    )
