"""Secrets API — file state, md5, cookie names, download."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from web.deps import FILES, file_info, run_check

router = APIRouter()


@router.get("/secrets/state")
async def secrets_state() -> dict:
    """Snapshot of salt/creds/cookies in /data and /app."""
    return {name: file_info(p) for name, p in FILES.items()}


@router.get("/secrets/check/{mode}")
async def secrets_check(mode: str) -> dict:
    """Run check_secrets.py in given mode: creds|cookies|session."""
    if mode not in ("creds", "cookies", "session"):
        raise HTTPException(400, "mode must be creds|cookies|session")
    return run_check(mode)


@router.get("/secrets/cookie-names")
async def cookie_names() -> dict:
    """List cookie NAMES only (no values) from decrypted session-cookies.txt."""
    res = run_check("cookies", timeout=15)
    if not res.get("ok"):
        return {"ok": False, "error": "cannot decrypt cookies", "detail": res}

    # We don't have plaintext here directly; use file on disk and extract names.
    # But file is encrypted. So re-use check_secrets to confirm then parse via login module.
    try:
        import sys
        sys.path.insert(0, "/app/owa-exchange-mcp")
        from login import decrypt_cookie_file
        import os

        mf = os.environ.get("EXCHANGE_MASTER_PASSWORD", "")
        if not mf:
            return {"ok": False, "error": "EXCHANGE_MASTER_PASSWORD not set"}

        cookies_file = Path("/app/owa-exchange-mcp/session-cookies.txt")
        raw = decrypt_cookie_file(mf, cookies_file)
        if not raw:
            return {"ok": False, "error": "decrypt returned empty"}

        names = []
        for line in raw.splitlines():
            if "=" in line:
                name = line.split("=", 1)[0].strip()
                if name:
                    names.append(name)
        return {"ok": True, "names": names, "count": len(names)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@router.get("/secrets/download/{name}")
async def download_secret(name: str) -> FileResponse:
    """Download an ENCRYPTED file from /data (safe — still encrypted)."""
    allowed = {
        "salt": FILES["salt_data"],
        "creds": FILES["creds_data"],
        "cookies": FILES["cookies_data"],
    }
    if name not in allowed:
        raise HTTPException(400, "allowed: salt|creds|cookies")
    path = allowed[name]
    if not path.is_file():
        raise HTTPException(404, f"{path} not found")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")
