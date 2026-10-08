#!/usr/bin/env python3
"""Web UI entry point — FastAPI on :8099, proxied by HA ingress."""
import os
import sys
import traceback

sys.path.insert(0, "/app")


def main() -> None:
    port = int(os.environ.get("WEB_UI_PORT", "8099"))
    print(f"[web] starting uvicorn on 0.0.0.0:{port}", flush=True)
    print(f"[web] sys.path[:3] = {sys.path[:3]}", flush=True)
    print(f"[web] cwd = {os.getcwd()}", flush=True)

    try:
        import uvicorn
        print(f"[web] uvicorn imported OK", flush=True)
    except Exception:
        print("[web] FATAL: cannot import uvicorn", flush=True)
        traceback.print_exc()
        sys.exit(1)

    try:
        import web.app as _wa
        print(f"[web] web.app imported OK, app={_wa.app}", flush=True)
    except Exception:
        print("[web] FATAL: cannot import web.app", flush=True)
        traceback.print_exc()
        sys.exit(2)

    try:
        uvicorn.run(
            _wa.app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=False,
        )
    except Exception:
        print("[web] FATAL: uvicorn.run raised", flush=True)
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
