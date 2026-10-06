FROM ghcr.io/home-assistant/aarch64-base-debian:latest

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        bash \
        curl \
        git \
        jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY owa-exchange-mcp /app/owa-exchange-mcp
COPY run_http.py /app/run_http.py
COPY run.sh /run.sh
COPY check_secrets.py /app/owa-exchange-mcp/check_secrets.py

# Bake venv + deps into the image so addon starts fast
WORKDIR /app/owa-exchange-mcp
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -e . && .venv/bin/pip install --no-cache-dir playwright
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
