"""Запуск MCP-сервера по HTTP (SSE) с автологином из env-переменной."""
import os
import sys
import traceback

def log(msg):
    print(f"[startup] {msg}", file=sys.stderr, flush=True)

MASTER_PASSWORD = os.environ.get("EXCHANGE_MASTER_PASSWORD")
log(f"MASTER_PASSWORD set: {bool(MASTER_PASSWORD)}")
log(f"EXCHANGE keys: {[k for k in os.environ if 'EXCHANGE' in k]}")
if MASTER_PASSWORD:
    log(f"MASTER_PASSWORD length: {len(MASTER_PASSWORD)}")

from exchange_mcp.owa_client import OWAClient

_original_load_cookies = OWAClient._load_cookies


def _patched_load_cookies(self):
    log(f"_patched_load_cookies CALLED, client_id={id(self)}, cookie_file={getattr(self, 'cookie_file', None)}")

    if getattr(self, "_cookies_loaded", False):
        log(f"_patched_load_cookies: already loaded, skipping")
        return

    if MASTER_PASSWORD:
        try:
            from exchange_mcp.auth import decrypt_cookie_file, decrypt_credentials

            log(f"_patched: try decrypt with pwd len={len(MASTER_PASSWORD)}")
            cookies_str = decrypt_cookie_file(MASTER_PASSWORD, self.cookie_file)

            if cookies_str:
                log(f"_patched: decrypted OK, len={len(cookies_str)}, first20={cookies_str[:20]!r}")
                self.load_cookies_from_string(cookies_str)
                self._cookies_loaded = True

                try:
                    username, _ = decrypt_credentials(MASTER_PASSWORD)
                    if username:
                        self.user_email = username
                        log(f"_patched: user_email={username}")
                except Exception as e:
                    log(f"_patched: user_email extract failed: {e}")

                log(f"_patched: DONE, returning (cookies loaded)")
                return
            else:
                log(f"_patched: decrypt returned EMPTY/None")
        except Exception as e:
            log(f"_patched: DECRYPT FAILED: {type(e).__name__}: {e}")
            log(f"_patched: traceback: {traceback.format_exc()}")
    else:
        log(f"_patched: MASTER_PASSWORD is empty at call time")

    log(f"_patched: falling through to _original_load_cookies")
    return _original_load_cookies(self)


OWAClient._load_cookies = _patched_load_cookies
log("OWAClient._load_cookies patched")

# ------------------------------------------------------------------
# Reactive re-login on HTTP 440 (SessionExpiredError).
# Upstream OWAClient.request retries once with the SAME cookies,
# which doesn't help if the server-side session expired.
# Hook: on SessionExpiredError -> run login.py via browserless
# -> force-reload cookies from disk -> retry once.
# ------------------------------------------------------------------
import subprocess
import threading
import time
import shutil
from pathlib import Path as _Path

from exchange_mcp.owa_client import SessionExpiredError

_login_lock = threading.Lock()
_last_login_ts = [0.0]
_LOGIN_COOLDOWN = 60.0


def _run_login() -> bool:
    """Run login.py via browserless to refresh cookies. Serialized."""
    with _login_lock:
        now = time.time()
        if now - _last_login_ts[0] < _LOGIN_COOLDOWN:
            log(f"login cooldown ({now - _last_login_ts[0]:.0f}s < {_LOGIN_COOLDOWN}s), skip")
            return False
        log("Running login.py via browserless (reactive re-login)...")
        try:
            r = subprocess.run(
                ["/app/owa-exchange-mcp/.venv/bin/python", "login.py"],
                cwd="/app/owa-exchange-mcp",
                capture_output=True,
                text=True,
                timeout=150,
            )
        except subprocess.TimeoutExpired:
            log("login.py TIMEOUT (>150s)")
            _last_login_ts[0] = time.time()
            return False
        _last_login_ts[0] = time.time()
        if r.returncode != 0:
            log(f"login.py exit={r.returncode}")
            log(f"login.py stderr tail: {r.stderr[-500:]}")
            return False
        log("login.py OK — cookies refreshed")
        for name in ("session-cookies.txt", ".salt", ".credentials.enc"):
            src = _Path("/app/owa-exchange-mcp") / name
            dst = _Path("/data") / name
            if src.exists():
                try:
                    shutil.copy(src, dst)
                except Exception as e:
                    log(f"copy {name} -> /data failed: {e}")
        return True


_original_request = OWAClient.request


def _patched_request(self, action, payload, *, timeout=30):
    try:
        return _original_request(self, action, payload, timeout=timeout)
    except SessionExpiredError as e:
        log(f"SessionExpiredError on action={action}: {e}")
        if not _run_login():
            log("re-login failed or skipped — re-raising")
            raise
        try:
            self._cookies_loaded = False
            self._loaded = False
            self.reload_cookies()
            log("cookies reloaded after login")
        except Exception as reload_err:
            log(f"reload_cookies after login failed: {reload_err}")
            raise
        log(f"retrying action={action} with fresh cookies...")
        return _original_request(self, action, payload, timeout=timeout)


OWAClient.request = _patched_request
log("OWAClient.request patched: reactive re-login on 440")


# ------------------------------------------------------------------
# Fix: tools/auth.py (line 147) imports decrypt_credentials/decrypt_cookie_file
# *inside* the tool function and calls them with the `master_password`
# argument supplied by the LLM (usually None/empty) -> "Invalid master password".
# Force env MASTER_PASSWORD for all decrypt_* calls. Because the import in
# tools/auth.py is function-local, patching the module attribute is enough —
# no need to touch consumer modules.
# ------------------------------------------------------------------
import exchange_mcp.auth as _auth

if MASTER_PASSWORD:
    _orig_decrypt_creds = _auth.decrypt_credentials

    def _patched_decrypt_creds(_master_password=None):
        return _orig_decrypt_creds(MASTER_PASSWORD)

    _auth.decrypt_credentials = _patched_decrypt_creds

    _orig_decrypt_cookie = _auth.decrypt_cookie_file

    def _patched_decrypt_cookie(_master_password=None, cookie_file=None):
        return _orig_decrypt_cookie(MASTER_PASSWORD, cookie_file)

    _auth.decrypt_cookie_file = _patched_decrypt_cookie

    log("exchange_mcp.auth.decrypt_* patched: force MASTER_PASSWORD from env")
else:
    log("WARNING: MASTER_PASSWORD empty — exchange_mcp.auth.decrypt_* NOT patched")



from exchange_mcp.server import mcp

mcp.settings.host = "0.0.0.0"
mcp.settings.port = 8765

try:
    sec = mcp.settings.transport_security
    sec.enable_dns_rebinding_protection = False
    if hasattr(sec, "allowed_hosts"):
        sec.allowed_hosts.append("innately-ultimate-dachshund.cloudpub.ru")
        sec.allowed_hosts.append("innately-ultimate-dachshund.cloudpub.ru:443")
    log(f"allowed_hosts={getattr(sec, 'allowed_hosts', None)}")
except Exception as e:
    log(f"transport_security: {e}")


if __name__ == "__main__":
    if not MASTER_PASSWORD:
        log("WARNING: EXCHANGE_MASTER_PASSWORD не задан")
    mcp.run(transport="sse")
