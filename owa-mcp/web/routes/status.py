"""Status API — files, creds, cookies, session."""
from __future__ import annotations

from fastapi import APIRouter

from web.deps import session_status, supervisor_logs

router = APIRouter()


def get_status_data() -> dict:
    """Used by both HTML page and JSON API."""
    return session_status()


@router.get("/status")
async def api_status() -> dict:
    return session_status()


@router.get("/logs/tail")
async def api_logs_tail(lines: int = 200) -> dict:
    return supervisor_logs(lines=lines)
