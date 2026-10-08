"""Actions API — force re-login, session check, etc."""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from web.deps import APP_DIR, VENV_PY

router = APIRouter()

# In-memory state of the last/current login attempt
_login_lock = threading.Lock()
_login_state: dict = {
    "running": False,
    "started_at": 0.0,
    "finished_at": 0.0,
    "ok": None,
    "log": [],
    "returncode": None,
}


def _append_log(line: str) -> None:
    _login_state["log"].append(line)
    # keep last 200 lines
    _login_state["log"] = _login_state["log"][-200:]


def _run_login() -> None:
    _login_state["running"] = True
    _login_state["started_at"] = time.time()
    _login_state["finished_at"] = 0.0
    _login_state["ok"] = None
    _login_state["returncode"] = None
    _login_state["log"] = []

    login_py = APP_DIR / "login.py"
    if not login_py.is_file():
        _append_log(f"ERROR: {login_py} not found")
        _login_state["running"] = False
        _login_state["ok"] = False
        _login_state["finished_at"] = time.time()
        return

    _append_log(f"$ {VENV_PY} {login_py}")
    try:
        r = subprocess.run(
            [str(VENV_PY), str(login_py)],
            cwd=str(APP_DIR),
            capture_output=True,
            text=True,
            timeout=180,
        )
        for line in (r.stdout or "").splitlines():
            _append_log(line)
        for line in (r.stderr or "").splitlines():
            _append_log("[stderr] " + line)
        _login_state["returncode"] = r.returncode
        _login_state["ok"] = r.returncode == 0
        if r.returncode == 0:
            # copy fresh secrets to /data
            for name in ("session-cookies.txt", ".salt", ".credentials.enc"):
                src = APP_DIR / name
                dst = Path("/data") / name
                if src.is_file():
                    try:
                        dst.write_bytes(src.read_bytes())
                        _append_log(f"copied {name} -> /data/")
                    except Exception as e:
                        _append_log(f"copy {name} failed: {e}")
    except subprocess.TimeoutExpired:
        _append_log("ERROR: login.py TIMEOUT (>180s)")
        _login_state["ok"] = False
        _login_state["returncode"] = -1
    except Exception as e:
        _append_log(f"ERROR: {type(e).__name__}: {e}")
        _login_state["ok"] = False
        _login_state["returncode"] = -1
    finally:
        _login_state["running"] = False
        _login_state["finished_at"] = time.time()


@router.post("/actions/re-login")
async def force_re_login() -> dict:
    """Start login.py in background thread."""
    with _login_lock:
        if _login_state["running"]:
            return {"ok": False, "error": "login already running", "state": _login_state}
        t = threading.Thread(target=_run_login, daemon=True)
        t.start()
        return {"ok": True, "message": "re-login started"}


@router.get("/actions/re-login/status")
async def re_login_status() -> dict:
    """Poll current login state."""
    return _login_state
