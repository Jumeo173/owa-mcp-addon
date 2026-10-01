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
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
