#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting OWA Exchange MCP add-on..."

ADDON_CONFIG="/config"
mkdir -p "${ADDON_CONFIG}"

ENV_FILE_NAME=$(bashio::config 'env_file')
ENV_FILE="${ADDON_CONFIG}/${ENV_FILE_NAME}"

if [ ! -f "${ENV_FILE}" ]; then
    bashio::log.fatal "Env file not found: ${ENV_FILE}"
    exit 1
fi

bashio::log.info "Using env file: ${ENV_FILE}"

COOKIES_SRC="${ADDON_CONFIG}/session-cookies.txt"
if [ -f "${COOKIES_SRC}" ]; then
    cp "${COOKIES_SRC}" /app/owa-exchange-mcp/session-cookies.txt
    bashio::log.info "Cookies copied."
else
    bashio::log.warning "session-cookies.txt не найден в ${ADDON_CONFIG}/"
fi

SALT_SRC="${ADDON_CONFIG}/.salt"
if [ -f "${SALT_SRC}" ]; then
    cp "${SALT_SRC}" /app/owa-exchange-mcp/.salt
    bashio::log.info "Salt copied."
else
    bashio::log.warning ".salt не найден в ${ADDON_CONFIG}/"
fi

CREDS_SRC="${ADDON_CONFIG}/.credentials.enc"
if [ -f "${CREDS_SRC}" ]; then
    cp "${CREDS_SRC}" /app/owa-exchange-mcp/.credentials.enc
    bashio::log.info "Credentials copied."
else
    bashio::log.warning ".credentials.enc не найден в ${ADDON_CONFIG}/"
fi

cd /app/owa-exchange-mcp
if [ ! -d ".venv" ]; then
    bashio::log.info "Creating venv (first run, может занять 2-5 минут)..."
    python3 -m venv .venv
    .venv/bin/pip install --no-cache-dir -e .
fi

set -a
source "${ENV_FILE}"
set +a

cd /app
bashio::log.info "Launching run_http.py..."
exec /app/owa-exchange-mcp/.venv/bin/python -u /app/run_http.py
