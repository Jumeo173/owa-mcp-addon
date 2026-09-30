"""Запуск MCP-сервера по HTTP (SSE) с автологином из env-переменной."""
import os

MASTER_PASSWORD = os.environ.get("EXCHANGE_MASTER_PASSWORD")

from exchange_mcp.owa_client import OWAClient

_original_load_cookies = OWAClient._load_cookies


def _patched_load_cookies(self):
    if getattr(self, "_cookies_loaded", False):
        return

    if MASTER_PASSWORD:
        try:
            from exchange_mcp.auth import decrypt_cookie_file, decrypt_credentials
            cookies_str = decrypt_cookie_file(MASTER_PASSWORD, self.cookie_file)
            if cookies_str:
                self.load_cookies_from_string(cookies_str)
                self._cookies_loaded = True
                try:
                    username, _ = decrypt_credentials(MASTER_PASSWORD)
                    if username:
                        self.user_email = username
                        print(f"[startup] client id={id(self)}, user_email={username}")
                except Exception as e:
                    print(f"[startup] Не удалось получить username: {e}")
                print(f"[startup] Cookies расшифрованы (client id={id(self)})")
                return
        except Exception as e:
            print(f"[startup] Не удалось расшифровать куки: {e}")

    return _original_load_cookies(self)


OWAClient._load_cookies = _patched_load_cookies

from exchange_mcp.server import mcp

mcp.settings.host = "0.0.0.0"
mcp.settings.port = 8765

try:
    sec = mcp.settings.transport_security
    sec.enable_dns_rebinding_protection = False
    if hasattr(sec, "allowed_hosts"):
        sec.allowed_hosts.append("comically-helping-bellbird.cloudpub.ru")
        sec.allowed_hosts.append("comically-helping-bellbird.cloudpub.ru:443")
    print(f"[startup] allowed_hosts={getattr(sec, 'allowed_hosts', None)}")
except Exception as e:
    print(f"[startup] transport_security: {e}")

if __name__ == "__main__":
    if not MASTER_PASSWORD:
        print("[startup] WARNING: EXCHANGE_MASTER_PASSWORD не задан")
    mcp.run(transport="sse")
