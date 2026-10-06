#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting OWA Exchange MCP add-on (v0.4.1)..."

DATA_DIR="/data"
LEGACY_CONFIG="/config"
MIGRATION_FLAG="${DATA_DIR}/.migration_done"

COOKIES_SRC="${DATA_DIR}/session-cookies.txt"
SALT_SRC="${DATA_DIR}/.salt"
CREDS_SRC="${DATA_DIR}/.credentials.enc"

export EXCHANGE_OWA_URL=$(bashio::config 'exchange_owa_url')
export EXCHANGE_MASTER_PASSWORD=$(bashio::config 'exchange_master_password')
export EXCHANGE_EMAIL=$(bashio::config 'exchange_email')
export EXCHANGE_PASSWORD=$(bashio::config 'exchange_password')
export BROWSERLESS_WS=$(bashio::config 'browserless_ws')

bashio::log.info "OWA URL: ${EXCHANGE_OWA_URL}"
bashio::log.info "Email: ${EXCHANGE_EMAIL}"
bashio::log.info "Master password set: $([ -n "${EXCHANGE_MASTER_PASSWORD}" ] && echo yes || echo no)"
bashio::log.info "OWA password set: $([ -n "${EXCHANGE_PASSWORD}" ] && echo yes || echo no)"
bashio::log.info "BROWSERLESS_WS: ${BROWSERLESS_WS}"

if [ ! -f "${MIGRATION_FLAG}" ] && [ -f "${LEGACY_CONFIG}/session-cookies.txt" ]; then
    bashio::log.warning "=== Migrate from /config to /data ==="

    cp -f "${LEGACY_CONFIG}/session-cookies.txt" "${COOKIES_SRC}" 2>/dev/null && bashio::log.info "  session-cookies.txt -> /data/"
    cp -f "${LEGACY_CONFIG}/.salt" "${SALT_SRC}" 2>/dev/null && bashio::log.info "  .salt -> /data/"
    cp -f "${LEGACY_CONFIG}/.credentials.enc" "${CREDS_SRC}" 2>/dev/null && bashio::log.info "  .credentials.enc -> /data/"

    if [ -f "${LEGACY_CONFIG}/owa-mcp.env" ]; then
        bashio::log.warning "=== Old values from owa-mcp.env ==="
        while IFS='=' read -r key value; do
            case "$key" in
                EXCHANGE_OWA_URL)         bashio::log.warning "  exchange_owa_url = ${value}" ;;
                EXCHANGE_MASTER_PASSWORD) bashio::log.warning "  exchange_master_password = ${value}" ;;
                EXCHANGE_EMAIL)           bashio::log.warning "  exchange_email = ${value}" ;;
                EXCHANGE_PASSWORD)        bashio::log.warning "  exchange_password = ${value}" ;;
                BROWSERLESS_WS)           bashio::log.warning "  browserless_ws = ${value}" ;;
            esac
        done < "${LEGACY_CONFIG}/owa-mcp.env"
        bashio::log.warning "========================================="
    fi

    touch "${MIGRATION_FLAG}"
    bashio::log.info "Migration done."
fi

if [ -f "${COOKIES_SRC}" ]; then cp "${COOKIES_SRC}" /app/owa-exchange-mcp/session-cookies.txt; bashio::log.info "Cookies copied."; fi
if [ -f "${SALT_SRC}" ]; then cp "${SALT_SRC}" /app/owa-exchange-mcp/.salt; bashio::log.info "Salt copied."; fi
if [ -f "${CREDS_SRC}" ]; then cp "${CREDS_SRC}" /app/owa-exchange-mcp/.credentials.enc; bashio::log.info "Credentials copied."; fi

cd /app/owa-exchange-mcp
if [ ! -d ".venv" ]; then
    bashio::log.info "Creating venv..."
    python3 -m venv .venv
    .venv/bin/pip install --no-cache-dir -e .
    .venv/bin/pip install --no-cache-dir playwright
fi

NEED_SETUP=0
if [ ! -f "${CREDS_SRC}" ] || [ ! -f "${SALT_SRC}" ]; then
    NEED_SETUP=1
elif [ -z "${EXCHANGE_MASTER_PASSWORD}" ] || [ -z "${EXCHANGE_EMAIL}" ] || [ -z "${EXCHANGE_PASSWORD}" ]; then
    bashio::log.warning "Fill exchange_master_password, exchange_email, exchange_password in UI"
    NEED_SETUP=1
else
    if ! .venv/bin/python /app/owa-exchange-mcp/check_secrets.py creds 2>/dev/null; then
        bashio::log.warning "Credentials not decryptable, recreating"
        NEED_SETUP=1
    fi
fi

if [ "${NEED_SETUP}" = "1" ]; then
    if [ -z "${EXCHANGE_EMAIL}" ] || [ -z "${EXCHANGE_PASSWORD}" ] || [ -z "${EXCHANGE_MASTER_PASSWORD}" ]; then
        bashio::log.fatal "Fill UI fields and restart"
        exit 1
    fi
    bashio::log.info "Running login.py --setup..."
    if .venv/bin/python login.py --setup; then
        bashio::log.info "Setup OK"
        cp -f /app/owa-exchange-mcp/.credentials.enc "${CREDS_SRC}" 2>/dev/null || true
        cp -f /app/owa-exchange-mcp/.salt "${SALT_SRC}" 2>/dev/null || true
    else
        bashio::log.error "Setup failed"
        exit 1
    fi
fi

NEED_LOGIN=0
if [ ! -f "${COOKIES_SRC}" ]; then
    NEED_LOGIN=1
else
    if ! .venv/bin/python /app/owa-exchange-mcp/check_secrets.py cookies 2>/dev/null; then
        bashio::log.warning "Cookies not decryptable, running login.py"
        NEED_LOGIN=1
    fi
fi

if [ "${NEED_LOGIN}" = "1" ]; then
    bashio::log.info "Running login.py via browserless..."
    if .venv/bin/python login.py; then
        bashio::log.info "login.py OK"
        cp -f /app/owa-exchange-mcp/session-cookies.txt "${COOKIES_SRC}" 2>/dev/null || true
        cp -f /app/owa-exchange-mcp/.salt "${SALT_SRC}" 2>/dev/null || true
        cp -f /app/owa-exchange-mcp/.credentials.enc "${CREDS_SRC}" 2>/dev/null || true
    else
        bashio::log.error "login.py failed"
    fi
fi

COOKIES_OK=0
if [ -f "/app/owa-exchange-mcp/session-cookies.txt" ]; then
    if .venv/bin/python /app/owa-exchange-mcp/check_secrets.py cookies 2>/dev/null; then
        COOKIES_OK=1
    fi
fi

if [ "${COOKIES_OK}" = "1" ] && [ -f "${MIGRATION_FLAG}" ]; then
    [ -f "${LEGACY_CONFIG}/owa-mcp.env" ] && [ ! -f "${LEGACY_CONFIG}/owa-mcp.env.old" ] && mv "${LEGACY_CONFIG}/owa-mcp.env" "${LEGACY_CONFIG}/owa-mcp.env.old" && bashio::log.info "Legacy: owa-mcp.env -> .old"
    [ -f "${LEGACY_CONFIG}/session-cookies.txt" ] && [ ! -f "${LEGACY_CONFIG}/session-cookies.txt.old" ] && mv "${LEGACY_CONFIG}/session-cookies.txt" "${LEGACY_CONFIG}/session-cookies.txt.old" && bashio::log.info "Legacy: cookies -> .old"
    [ -f "${LEGACY_CONFIG}/.salt" ] && [ ! -f "${LEGACY_CONFIG}/.salt.old" ] && mv "${LEGACY_CONFIG}/.salt" "${LEGACY_CONFIG}/.salt.old" && bashio::log.info "Legacy: .salt -> .old"
    [ -f "${LEGACY_CONFIG}/.credentials.enc" ] && [ ! -f "${LEGACY_CONFIG}/.credentials.enc.old" ] && mv "${LEGACY_CONFIG}/.credentials.enc" "${LEGACY_CONFIG}/.credentials.enc.old" && bashio::log.info "Legacy: .credentials.enc -> .old"
    bashio::log.info "Legacy files renamed to .old"
fi

cd /app
bashio::log.info "Launching run_http.py..."
exec /app/owa-exchange-mcp/.venv/bin/python -u /app/run_http.py
