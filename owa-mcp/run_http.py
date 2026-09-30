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
