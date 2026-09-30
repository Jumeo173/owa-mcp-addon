FROM ghcr.io/home-assistant/aarch64-base:latest

RUN apk add --no-cache bash curl

ARG CLO_URL=https://cloudpub.ru/download/stable/clo-3.5.1056-stable-linux-aarch64.tar.gz
RUN cd /tmp && \
    curl -fsSL "${CLO_URL}" -o clo.tar.gz && \
    tar -xzf clo.tar.gz && \
    mv clo /usr/local/bin/clo && \
    chmod +x /usr/local/bin/clo && \
    rm -f clo.tar.gz

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
