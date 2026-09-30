ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache \
        python3 \
        py3-pip \
        py3-virtualenv \
        chromium \
        chromium-chromedriver \
        xvfb \
        ttf-freefont \
        bash \
        curl \
        git \
        jq

WORKDIR /app

COPY owa-exchange-mcp /app/owa-exchange-mcp
COPY run_http.py /app/run_http.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
