"""Utilities for managing refresh token sessions in Redis."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import TypedDict

from fastapi import Response

from src.core.cache.client import get_redis_client
from src.core.config import get_settings

settings = get_settings()


class RefreshSession(TypedDict):
    architect_id: str
    issued_at: float


_SESSION_PREFIX = "auth:session"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_key(token: str) -> str:
    return f"{_SESSION_PREFIX}:{token}"


def _ttl_seconds() -> int:
    return int(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)


async def create_session(architect_id: str) -> str:
    token = secrets.token_urlsafe(32)
    hashed = _hash_token(token)
    key = _session_key(hashed)
    payload: RefreshSession = {"architect_id": architect_id, "issued_at": time.time()}
    client = get_redis_client()
    await client.set(key, json.dumps(payload), ex=_ttl_seconds())
    return token


async def get_session(token: str) -> RefreshSession | None:
    hashed = _hash_token(token)
    key = _session_key(hashed)
    client = get_redis_client()
    raw = await client.get(key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        if "architect_id" not in data:
            return None
        return RefreshSession(
            architect_id=str(data["architect_id"]), issued_at=float(data.get("issued_at", 0))
        )
    except Exception:
        return None


async def delete_session(token: str) -> None:
    hashed = _hash_token(token)
    key = _session_key(hashed)
    client = get_redis_client()
    try:
        await client.delete(key)
    except Exception:
        pass


async def replace_session(old_token: str | None, architect_id: str) -> str:
    if old_token:
        await delete_session(old_token)
    return await create_session(architect_id)


def set_refresh_cookie(response: Response, token: str) -> None:
    max_age = _ttl_seconds()
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN,
        max_age=max_age,
        expires=max_age,
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN,
        path="/",
    )
