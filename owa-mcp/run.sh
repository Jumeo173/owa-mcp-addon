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

# === МИГРАЦИЯ из /config в /data (только при первом запуске) ===
if [ ! -f "${MIGRATION_FLAG}" ] && [ -f "${LEGACY_CONFIG}/session-cookies.txt" ]; then
    bashio::log.warning "=== Миграция из ${LEGACY_CONFIG} в ${DATA_DIR} ==="

    cp -f "${LEGACY_CONFIG}/session-cookies.txt" "${COOKIES_SRC}" 2>/dev/null && \
        bashio::log.info "  session-cookies.txt → /data/"
    cp -f "${LEGACY_CONFIG}/.salt" "${SALT_SRC}" 2>/dev/null && \
        bashio::log.info "  .salt → /data/"
    cp -f "${LEGACY_CONFIG}/.credentials.enc" "${CREDS_SRC}" 2>/dev/null && \
        bashio::log.info "  .credentials.enc → /data/"

    if [ -f "${LEGACY_CONFIG}/owa-mcp.env" ]; then
        bashio::log.warning ""
        bashio::log.warning "=== ВНИМАНИЕ: старые значения из ${LEGACY_CONFIG}/owa-mcp.env ==="
        bashio::log.warning "Открой Configuration UI и заполни поля этими значениями:"
        while IFS='=' read -r key value; do
            case "$key" in
                EXCHANGE_OWA_URL)         bashio::log.warning "  exchange_owa_url = ${value}" ;;
                EXCHANGE_MASTER_PASSWORD) bashio::log.warning "  exchange_master_password = ${value}" ;;
                EXCHANGE_EMAIL)           bashio::log.warning "  exchange_email = ${value}" ;;
                EXCHANGE_PASSWORD)        bashio::log.warning "  exchange_password = ${value}" ;;
                BROWSERLESS_WS)           bashio::log.warning "  browserless_ws = ${value}" ;;
            esac
        done < "${LEGACY_CONFIG}/owa-mcp.env"
        bashio::log.warning "===================================================="
        bashio::log.warning ""
    fi

    touch "${MIGRATION_FLAG}"
    bashio::log.info "Миграция завершена. Cookies/salt/credentials в /data/"
fi

# Копируем файлы из /data в рабочую директорию
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

NEED_SETUP=0
if [ ! -f "${CREDS_SRC}" ] || [ ! -f "${SALT_SRC}" ]; then
    bashio::log.warning "Credentials/salt отсутствуют — нужен setup"
    NEED_SETUP=1
elif [ -z "${EXCHANGE_MASTER_PASSWORD}" ] || [ -z "${EXCHANGE_EMAIL}" ] || [ -z "${EXCHANGE_PASSWORD}" ]; then
    bashio::log.warning "Не все поля заполнены в UI: master/email/password"
    bashio::log.warning "Заполни Configuration и перезапусти аддон"
    NEED_SETUP=1
else
    if ! .venv/bin/python -c "
import os, sys
sys.path.insert(0, '/app/owa-exchange-mcp')
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from pathlib import Path

def get_key(password, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

mf = os.environ.get('EXCHANGE_MASTER_PASSWORD', '')
salt = Path('/app/owa-exchange-mcp/.salt').read_bytes()
enc = Path('/app/owa-exchange-mcp/.credentials.enc').read_bytes()
try:
    Fernet(get_key(mf, salt)).decrypt(enc)
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        bashio::log.warning ".credentials.enc не расшифровывается — пересоздаю"
        NEED_SETUP=1
    fi
fi

if [ "${NEED_SETUP}" = "1" ]; then
    if [ -z "${EXCHANGE_EMAIL}" ] || [ -z "${EXCHANGE_PASSWORD}" ] || [ -z "${EXCHANGE_MASTER_PASSWORD}" ]; then
        bashio::log.fatal "Заполни exchange_email, exchange_password, exchange_master_password в UI аддона и перезапусти"
        exit 1
    fi
    bashio::log.info "Запуск login.py --setup..."
    cd /app/owa-exchange-mcp
    if .venv/bin/python login.py --setup; then
        bashio::log.info "Setup OK"
        cp -f /app/owa-exchange-mcp/.credentials.enc "${CREDS_SRC}" 2>/dev/null || true
        cp -f /app/owa-exchange-mcp/.salt "${SALT_SRC}" 2>/dev/null || true
    else
        bashio::log.error "Setup упал"
        exit 1
    fi
fi

NEED_LOGIN=0
if [ ! -f "${COOKIES_SRC}" ]; then
    NEED_LOGIN=1
else
    if ! .venv/bin/python -c "
import os, sys
sys.path.insert(0, '/app/owa-exchange-mcp')
from exchange_mcp.auth import decrypt_cookie_file
from pathlib import Path
mf = os.environ.get('EXCHANGE_MASTER_PASSWORD', '')
try:
    r = decrypt_cookie_file(mf, Path('/app/owa-exchange-mcp/session-cookies.txt'))
    sys.exit(0 if r else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        bashio::log.warning "Cookies не расшифровались — запускаю login.py"
        NEED_LOGIN=1
    fi
fi

if [ "${NEED_LOGIN}" = "1" ]; then
    bashio::log.info "Запуск login.py через browserless..."
    cd /app/owa-exchange-mcp
    if .venv/bin/python login.py; then
        bashio::log.info "login.py OK"
        cp -f /app/owa-exchange-mcp/session-cookies.txt "${COOKIES_SRC}" 2>/dev/null || true
        cp -f /app/owa-exchange-mcp/.salt "${SALT_SRC}" 2>/dev/null || true
        cp -f /app/owa-exchange-mcp/.credentials.enc "${CREDS_SRC}" 2>/dev/null || true
    else
        bashio::log.error "login.py упал. Продолжаем со старыми cookies."
    fi
fi

# === Проверка: если cookies успешно расшифровались в этом запуске — переименовываем legacy-файлы в .old ===
COOKIES_OK=0
if [ -f "/app/owa-exchange-mcp/session-cookies.txt" ]; then
    if .venv/bin/python -c "
import os, sys
sys.path.insert(0, '/app/owa-exchange-mcp')
from exchange_mcp.auth import decrypt_cookie_file
from pathlib import Path
mf = os.environ.get('EXCHANGE_MASTER_PASSWORD', '')
try:
    r = decrypt_cookie_file(mf, Path('/app/owa-exchange-mcp/session-cookies.txt'))
    sys.exit(0 if r else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        COOKIES_OK=1
    fi
fi

if [ "${COOKIES_OK}" = "1" ] && [ -f "${MIGRATION_FLAG}" ]; then
    # Переименовываем legacy-файлы в .old (только если они ещё не переименованы)
    if [ -f "${LEGACY_CONFIG}/owa-mcp.env" ] && [ ! -f "${LEGACY_CONFIG}/owa-mcp.env.old" ]; then
        mv "${LEGACY_CONFIG}/owa-mcp.env" "${LEGACY_CONFIG}/owa-mcp.env.old" && \
            bashio::log.info "Legacy: owa-mcp.env → owa-mcp.env.old"
    fi
    if [ -f "${LEGACY_CONFIG}/session-cookies.txt" ] && [ ! -f "${LEGACY_CONFIG}/session-cookies.txt.old" ]; then
        mv "${LEGACY_CONFIG}/session-cookies.txt" "${LEGACY_CONFIG}/session-cookies.txt.old" && \
            bashio::log.info "Legacy: session-cookies.txt → session-cookies.txt.old"
    fi
    if [ -f "${LEGACY_CONFIG}/.salt" ] && [ ! -f "${LEGACY_CONFIG}/.salt.old" ]; then
        mv "${LEGACY_CONFIG}/.salt" "${LEGACY_CONFIG}/.salt.old" && \
            bashio::log.info "Legacy: .salt → .salt.old"
    fi
    if [ -f "${LEGACY_CONFIG}/.credentials.enc" ] && [ ! -f "${LEGACY_CONFIG}/.credentials.enc.old" ]; then
        mv "${LEGACY_CONFIG}/.credentials.enc" "${LEGACY_CONFIG}/.credentials.enc.old" && \
            bashio::log.info "Legacy: .credentials.enc → .credentials.enc.old"
    fi
    bashio::log.info "Legacy-файлы переименованы в .old (можно удалить вручную)"
fi

cd /app
bashio::log.info "Launching run_http.py..."
exec /app/owa-exchange-mcp/.venv/bin/python -u /app/run_http.py
