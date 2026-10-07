#!/usr/bin/env python3
"""
check_secrets.py — verify that encrypted credentials/cookies
can be decrypted with the current master password.

Uses the real functions from login.py / exchange_mcp.auth,
so it can never diverge from what run_http.py does.
"""
import os
import sys
from pathlib import Path

mode = sys.argv[1] if len(sys.argv) > 1 else "creds"

mf = os.environ.get("EXCHANGE_MASTER_PASSWORD", "")
if not mf:
    sys.exit(1)

sys.path.insert(0, "/app/owa-exchange-mcp")

if mode == "creds":
    try:
        from login import decrypt_credentials
        username, _ = decrypt_credentials(mf)
        sys.exit(0 if username else 1)
    except Exception as e:
        print(f"check_secrets creds: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

if mode == "cookies":
    try:
        from exchange_mcp.auth import decrypt_cookie_file
        cookies = decrypt_cookie_file(
            mf, Path("/app/owa-exchange-mcp/session-cookies.txt")
        )
        sys.exit(0 if cookies else 1)
    except Exception as e:
        print(f"check_secrets cookies: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

sys.exit(1)
if mode == "session":
    try:
        from login import decrypt_cookie_file
        from exchange_mcp.owa_client import OWAClient
        cookie_file = Path("/app/owa-exchange-mcp/session-cookies.txt")
        cookies_str = decrypt_cookie_file(mf, cookie_file)
        if not cookies_str:
            print("session: cannot decrypt cookies", file=sys.stderr)
            sys.exit(1)
        client = OWAClient()
        client.load_cookies_from_string(cookies_str)
        payload = {
            "__type": "GetFolderJsonRequest:#Exchange",
            "Header": {
                "__type": "JsonRequestHeaders:#Exchange",
                "RequestServerVersion": "Exchange2013",
            },
            "FolderShape": {
                "__type": "FolderResponseShape:#Exchange",
                "BaseShape": "IdOnly",
            },
            "Folders": [{
                "__type": "TargetFolderId:#Exchange",
                "BaseFolderId": {
                    "__type": "DistinguishedFolderId:#Exchange",
                    "Id": "inbox",
                },
            }],
        }
        client.request("GetFolder", payload, timeout=15)
        sys.exit(0)
    except Exception as e:
        print(f"session check: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

sys.exit(1)
