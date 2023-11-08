FROM node:16.16.0-bullseye-slim@sha256:cda7229eb72b7534396e7b58ba5b9f2454aee188317e058cbbf22686e5d07e2f AS console
WORKDIR /console
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./
RUN npm test && npm run build

FROM python:3.10.11-slim-bullseye@sha256:fd86924ba14682eb11a3c244f60a35b5dfe3267cbf26d883fb5c14813ce926f1
ARG TARGETARCH
RUN test "$TARGETARCH" = arm64
WORKDIR /app
COPY requirements-linux-arm64.lock ./
RUN pip install --no-cache-dir --no-deps --require-hashes -r requirements-linux-arm64.lock && pip check
COPY gateway/ ./gateway/
COPY --from=console /console/dist/ ./gateway/static/
RUN mkdir -p /data && chown 65532:65532 /data
ENV GATEWAY_DATABASE=/data/gateway.sqlite TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1 TRANSFORMERS_CACHE=/tmp/transformers HF_HUB_OFFLINE=1
USER 65532:65532
EXPOSE 8093
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8093/health/ready', timeout=2)"
CMD ["python", "-m", "gateway", "--host", "0.0.0.0", "--port", "8093"]
