import os, sys
from pathlib import Path

mode = sys.argv[1] if len(sys.argv) > 1 else "creds"

mf = os.environ.get("EXCHANGE_MASTER_PASSWORD", "")
if not mf:
    sys.exit(1)

if mode == "creds":
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        import base64
        salt = Path("/app/owa-exchange-mcp/.salt").read_bytes()
        enc = Path("/app/owa-exchange-mcp/.credentials.enc").read_bytes()
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
        key = base64.urlsafe_b64encode(kdf.derive(mf.encode()))
        Fernet(key).decrypt(enc)
        sys.exit(0)
    except Exception:
        sys.exit(1)

if mode == "cookies":
    try:
        sys.path.insert(0, "/app/owa-exchange-mcp")
        from exchange_mcp.auth import decrypt_cookie_file
        r = decrypt_cookie_file(mf, Path("/app/owa-exchange-mcp/session-cookies.txt"))
        sys.exit(0 if r else 1)
    except Exception:
        sys.exit(1)

sys.exit(1)
