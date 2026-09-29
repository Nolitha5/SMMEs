# Build from the firebase-foundation-bootstrap repository root:
#   docker build -f apps/shared-platform/Dockerfile -t sme-shared-platform .
FROM node:22-bookworm-slim

ENV NODE_ENV=production \
    PORT=8790 \
    PROCESSING_PYTHON=/opt/venv/bin/python \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY apps/shared-platform/package.json ./apps/shared-platform/package.json
RUN cd apps/shared-platform && npm install --no-audit --no-fund

COPY apps/shared-platform ./apps/shared-platform
COPY vendor/florah-demand ./vendor/florah-demand
COPY vendor/customer-engagement-shared ./vendor/customer-engagement-shared

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r vendor/florah-demand/backend/requirements.txt

RUN cd apps/shared-platform \
    && npm run check \
    && npm run build \
    && npm run validate:process

EXPOSE 8790

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8790)+'/api/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["node", "apps/shared-platform/server/index.mjs"]
