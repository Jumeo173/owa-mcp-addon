"""Shared helpers for the OWA MCP Web UI."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
APP_DIR = Path("/app/owa-exchange-mcp")
DATA_DIR = Path("/data")

FILES = {
    "salt_data":     DATA_DIR / ".salt",
    "creds_data":    DATA_DIR / ".credentials.enc",
    "cookies_data":  DATA_DIR / "session-cookies.txt",
    "salt_app":      APP_DIR / ".salt",
    "creds_app":     APP_DIR / ".credentials.enc",
    "cookies_app":   APP_DIR / "session-cookies.txt",
}

VENV_PY       = APP_DIR / ".venv" / "bin" / "python"
CHECK_SECRETS = APP_DIR / "check_secrets.py"
OPTIONS_FILE  = DATA_DIR / "options.json"


# ----------------------------------------------------------------------
# Generic file info
# ----------------------------------------------------------------------
def file_info(path: Path) -> dict[str, Any]:
    """Return size/mtime/md5 for a file (or {exists: False})."""
    if not path.is_file():
        return {"exists": False, "path": str(path)}
    data = path.read_bytes()
    return {
        "exists": True,
        "path": str(path),
        "size": len(data),
        "md5": hashlib.md5(data).hexdigest(),
        "mtime": path.stat().st_mtime,
    }


def files_snapshot() -> dict[str, dict]:
    """Snapshot of all known secret files."""
    return {name: file_info(p) for name, p in FILES.items()}


# ----------------------------------------------------------------------
# check_secrets.py wrapper
# ----------------------------------------------------------------------
def run_check(mode: str, timeout: int = 25) -> dict[str, Any]:
    """Run check_secrets.py <mode>; return {ok, exit, stdout, stderr}."""
    if not CHECK_SECRETS.is_file():
        return {"ok": False, "exit": -1, "error": "check_secrets.py not found"}
    if not VENV_PY.is_file():
        return {"ok": False, "exit": -1, "error": f"venv python not found: {VENV_PY}"}
    try:
        r = subprocess.run(
            [str(VENV_PY), str(CHECK_SECRETS), mode],
            cwd=str(APP_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": r.returncode == 0,
            "exit": r.returncode,
            "stdout": r.stdout.strip(),
            "stderr": r.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit": -1, "error": f"timeout >{timeout}s"}


# ----------------------------------------------------------------------
# Options / secrets
# ----------------------------------------------------------------------
def read_options() -> dict[str, Any]:
    """Read /data/options.json (addon config)."""
    if not OPTIONS_FILE.is_file():
        return {}
    try:
        return json.loads(OPTIONS_FILE.read_text())
    except Exception as e:
        return {"__error": str(e)}


def mask_secret(key: str, value: Any) -> str:
    """Return a safe-to-display string for a secret."""
    if value is None or value == "":
        return "(not set)"
    s = str(value)
    if key in ("exchange_master_password", "exchange_password"):
        return f"*** ({len(s)} chars)"
    if key == "exchange_email":
        if "@" in s:
            user, _, domain = s.partition("@")
            return f"{user[:2]}***@{domain}"
        return f"{s[:2]}***"
    return s


# ----------------------------------------------------------------------
# Supervisor API (logs)
# ----------------------------------------------------------------------
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
SUPERVISOR_URL   = "http://supervisor"


def supervisor_logs(lines: int = 200) -> dict[str, Any]:
    """Fetch addon log tail via Supervisor API."""
    if not SUPERVISOR_TOKEN:
        return {"ok": False, "error": "SUPERVISOR_TOKEN not set"}
    url = f"{SUPERVISOR_URL}/addons/self/logs"
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.get(url, headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"})
        if r.status_code != 200:
            return {"ok": False, "error": f"HTTP {r.status_code}", "body": r.text[:300]}
        return {"ok": True, "lines": r.text.splitlines()[-lines:]}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ----------------------------------------------------------------------
# Overall status snapshot
# ----------------------------------------------------------------------
def session_status() -> dict[str, Any]:
    """Aggregate status: files + three check_secrets modes."""
    return {
        "version":     os.environ.get("ADDON_VERSION", "unknown"),
        "uptime":      _uptime_seconds(),
        "files":       files_snapshot(),
        "creds":       run_check("creds"),
        "cookies":     run_check("cookies"),
        "session":     run_check("session", timeout=20),
        "options":     _masked_options(),
    }


def _masked_options() -> dict[str, str]:
    opts = read_options()
    return {k: mask_secret(k, v) for k, v in opts.items()}


def _uptime_seconds() -> float:
    """Uptime of this web process (approx — from /proc/1)."""
    try:
        from pathlib import Path as _P
        st = _P("/proc/1").stat()
        import time
        return time.time() - st.st_mtime
    except Exception:
        return 0.0
