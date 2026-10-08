"""Logs API — tail, filter, download."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from web.deps import supervisor_logs

router = APIRouter()


@router.get("/logs")
async def get_logs(
    lines: int = Query(200, ge=10, le=10000),
    level: str = Query("", description="INFO|WARNING|ERROR|"),
    q: str = Query("", description="substring filter"),
) -> dict:
    """Return filtered log tail."""
    res = supervisor_logs(lines=lines)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "unknown"), "lines": []}

    raw = res["lines"]

    # Level filter
    if level:
        pref = f"[{level.upper()}]"
        raw = [ln for ln in raw if pref in ln]

    # Substring filter
    if q:
        ql = q.lower()
        raw = [ln for ln in raw if ql in ln.lower()]

    return {"ok": True, "lines": raw, "count": len(raw)}


@router.get("/logs/download", response_class=PlainTextResponse)
async def download_logs(
    lines: int = Query(2000, ge=10, le=50000),
    level: str = Query(""),
    q: str = Query(""),
) -> PlainTextResponse:
    """Download filtered log as .txt."""
    data = await get_logs(lines=lines, level=level, q=q)
    if not data.get("ok"):
        raise HTTPException(500, data.get("error", "log fetch failed"))
    body = "\n".join(data["lines"])
    headers = {"Content-Disposition": 'attachment; filename="owa-mcp-logs.txt"'}
    return PlainTextResponse(body, headers=headers, media_type="text/plain; charset=utf-8")
