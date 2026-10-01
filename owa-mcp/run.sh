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

set -a
source "${ENV_FILE}"
set +a

COOKIES_SRC="${ADDON_CONFIG}/session-cookies.txt"
SALT_SRC="${ADDON_CONFIG}/.salt"
CREDS_SRC="${ADDON_CONFIG}/.credentials.enc"

if [ -f "${COOKIES_SRC}" ]; then
    cp "${COOKIES_SRC}" /app/owa-exchange-mcp/session-cookies.txt
    bashio::log.info "Cookies copied."
fi
if [ -f "${SALT_SRC}" ]; then
    cp "${SALT_SRC}" /app/owa-exchange-mcp/.salt
    bashio::log.info "Salt copied."
fi
if [ -f "${CREDS_SRC}" ]; then
    cp "${CREDS_SRC}" /app/owa-exchange-mcp/.credentials.enc
    bashio::log.info "Credentials copied."
fi

cd /app/owa-exchange-mcp
if [ ! -d ".venv" ]; then
    bashio::log.info "Creating venv (first run, может занять 2-5 минут)..."
    python3 -m venv .venv
    .venv/bin/pip install --no-cache-dir -e .
    .venv/bin/pip install --no-cache-dir playwright
fi

NEED_LOGIN=0
if [ ! -f "${COOKIES_SRC}" ] || [ ! -f "${SALT_SRC}" ] || [ ! -f "${CREDS_SRC}" ]; then
    bashio::log.warning "Cookies/salt/credentials отсутствуют — нужен login"
    NEED_LOGIN=1
else
    if ! .venv/bin/python -c "
import sys
sys.path.insert(0, '/app/owa-exchange-mcp')
from exchange_mcp.auth import decrypt_cookie_file
from pathlib import Path
mf = '${EXCHANGE_MASTER_PASSWORD}'
try:
    r = decrypt_cookie_file(mf, Path('/app/owa-exchange-mcp/session-cookies.txt'))
    sys.exit(0 if r else 1)
except Exception as e:
    print(f'decrypt check failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
        bashio::log.warning "Cookies не расшифровались — запускаю login.py"
        NEED_LOGIN=1
    fi
fi

if [ "${NEED_LOGIN}" = "1" ]; then
    bashio::log.info "Запуск login.py через browserless..."
    export BROWSERLESS_WS="${BROWSERLESS_WS:-ws://db21ed7f_browserless-chrome:3000}"
    bashio::log.info "BROWSERLESS_WS=${BROWSERLESS_WS}"

    cd /app/owa-exchange-mcp
    if .venv/bin/python login.py; then
        bashio::log.info "login.py завершился успешно, копирую свежие файлы в ${ADDON_CONFIG}/"
        cp -f /app/owa-exchange-mcp/session-cookies.txt "${COOKIES_SRC}" 2>/dev/null || true
        cp -f /app/owa-exchange-mcp/.salt "${SALT_SRC}" 2>/dev/null || true
        cp -f /app/owa-exchange-mcp/.credentials.enc "${CREDS_SRC}" 2>/dev/null || true
        bashio::log.info "Свежие файлы скопированы в addon_config"
    else
        bashio::log.error "login.py не смог войти. Продолжаем со старыми cookies."
    fi
fi

cd /app
bashio::log.info "Launching run_http.py..."
exec /app/owa-exchange-mcp/.venv/bin/python -u /app/run_http.py
