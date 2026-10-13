# Лотерейный анализатор: интерфейс Next.js + движок на Python в одном образе.
#   docker compose up -d        → http://localhost:3000, автозапуск раз в час
FROM node:22-bookworm-slim AS web
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY next.config.ts tsconfig.json next-env.d.ts ./
COPY config config
COPY public public
COPY src src
RUN npm run build

FROM node:22-bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv tini \
 && rm -rf /var/lib/apt/lists/*
COPY python/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PYTHON_BIN=/opt/venv/bin/python \
    LOTTERY_DATA_DIR=/data \
    TZ=Europe/Moscow
COPY --from=web /app/node_modules node_modules
COPY --from=web /app/.next .next
COPY package.json next.config.ts tsconfig.json ./
COPY public public
COPY config config
COPY python python
COPY data/tirazh*.txt /app/data-seed/
COPY docker/entrypoint.sh /entrypoint.sh
VOLUME ["/data"]
EXPOSE 3000
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
