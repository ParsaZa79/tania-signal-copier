"""User-owned trading account routes."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..account_store import (
    create_account,
    get_user_setup_status,
    list_user_accounts,
    mark_account_setup_complete,
    set_user_active_account,
)
from ..dependencies import activate_account_runtime
from ..security import get_current_user

router = APIRouter()
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


class CreateAccountRequest(BaseModel):
    name: str = Field(default="Trading Account", min_length=1, max_length=80)


@router.get("")
@router.get("/")
async def list_accounts(current_user: CurrentUser) -> dict:
    setup = get_user_setup_status(current_user)
    return {
        "success": True,
        "accounts": list_user_accounts(current_user["id"]),
        "active_account_id": setup["active_account_id"],
        "setup_complete": setup["setup_complete"],
    }


@router.post("")
@router.post("/")
async def add_account(
    request: CreateAccountRequest,
    current_user: CurrentUser,
) -> dict:
    account = create_account(current_user["id"], request.name)
    accounts = list_user_accounts(current_user["id"])
    return {
        "success": True,
        "account": account,
        "accounts": accounts,
        "active_account_id": account["id"] if len(accounts) == 1 else None,
    }


@router.get("/setup-status")
async def setup_status(current_user: CurrentUser) -> dict:
    return {
        "success": True,
        **get_user_setup_status(current_user),
    }


@router.post("/setup-complete")
async def complete_account_setup(current_user: CurrentUser) -> dict:
    setup = get_user_setup_status(current_user)
    account_id = setup["active_account_id"]
    if not account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account setup required")
    try:
        account_status = mark_account_setup_complete(account_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return {
        "success": True,
        "account_status": account_status,
        "setup": get_user_setup_status(current_user),
    }


@router.put("/{account_id}/active")
async def set_active_account(
    account_id: str,
    current_user: CurrentUser,
) -> dict:
    try:
        account = set_user_active_account(current_user["id"], account_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    runtime_result = await asyncio.to_thread(activate_account_runtime, account["id"])
    return {
        "success": True,
        "account": account,
        "active_account_id": account["id"],
        "accounts": list_user_accounts(current_user["id"]),
        "runtime": {
            "success": bool(runtime_result.get("success")),
            "connected": bool(runtime_result.get("connected")),
            "error": runtime_result.get("error"),
        },
    }
