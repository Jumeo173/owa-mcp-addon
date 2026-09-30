#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting CloudPub tunnel..."

ADDON_CONFIG="/config"
CONFIG_DIR="/root/.config/cloudpub"
mkdir -p "${CONFIG_DIR}"

TOKEN_FILE="${ADDON_CONFIG}/token"
if [ ! -f "${TOKEN_FILE}" ]; then
    bashio::log.fatal "Token not found at ${TOKEN_FILE}"
    bashio::log.fatal "Положи токен CloudPub в addon_configs/<slug>_cloudpub/token"
    exit 1
fi

TOKEN="$(cat ${TOKEN_FILE})"

AGENT_ID="$(cat /proc/sys/kernel/random/uuid)"

cat > "${CONFIG_DIR}/client.toml" <<EOF
agent_id = "${AGENT_ID}"
server = "https://cloudpub.ru/"
token = "${TOKEN}"
heartbeat_timeout = 40
minimize_to_tray_on_close = false
minimize_to_tray_on_start = false

[transport]
type = "websocket"

[transport.tcp]
connect_timeout_secs = 30

[transport.tls]

[transport.websocket]
tls = true
EOF

PROTOCOL=$(bashio::config 'protocol')
TARGET=$(bashio::config 'target')

bashio::log.info "Publishing ${PROTOCOL} ${TARGET}..."
exec /usr/local/bin/clo -v publish "${PROTOCOL}" "${TARGET}"
