#!/usr/bin/env python3
"""Web UI entry point — FastAPI on :8099, proxied by HA ingress."""
import os
import sys

sys.path.insert(0, "/app")

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("WEB_UI_PORT", "8099"))
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=False,
    )
