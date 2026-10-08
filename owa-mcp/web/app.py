"""FastAPI application for the OWA MCP Web UI."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).parent

app = FastAPI(title="OWA MCP", docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))


@app.get("/")
async def root():
    return RedirectResponse(url="/status")


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    from web.routes.status import get_status_data
    data = get_status_data()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "page": "status", **data},
    )


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    return templates.TemplateResponse(
        "logs.html",
        {"request": request, "page": "logs"},
    )


@app.get("/secrets", response_class=HTMLResponse)
async def secrets_page(request: Request):
    from web.routes.status import get_status_data
    data = get_status_data()
    return templates.TemplateResponse(
        "secrets.html",
        {"request": request, "page": "secrets", **data},
    )


@app.get("/actions", response_class=HTMLResponse)
async def actions_page(request: Request):
    return templates.TemplateResponse(
        "actions.html",
        {"request": request, "page": "actions"},
    )


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    from web.deps import _masked_options, read_options
    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "page": "config",
            "options": _masked_options(),
            "raw_keys": sorted(read_options().keys()),
        },
    )


from web.routes import status as _status_router   # noqa: E402, F401
from web.routes import logs as _logs_router       # noqa: E402, F401
from web.routes import secrets as _secrets_router # noqa: E402, F401
from web.routes import actions as _actions_router # noqa: E402, F401

app.include_router(_status_router.router,  prefix="/api", tags=["status"])
app.include_router(_logs_router.router,    prefix="/api", tags=["logs"])
app.include_router(_secrets_router.router, prefix="/api", tags=["secrets"])
app.include_router(_actions_router.router, prefix="/api", tags=["actions"])
