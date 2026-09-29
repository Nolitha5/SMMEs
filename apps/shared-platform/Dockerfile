# Production image for SME Operations.
# IMPORTANT: build from the repository root:
#   docker build -f apps/shared-platform/Dockerfile -t sme-shared-platform .
# The repository-root Dockerfile is canonical; this file mirrors it for hosts
# that require an explicit Dockerfile inside the application directory.

FROM node:22-bookworm-slim AS builder
ENV NODE_ENV=development
WORKDIR /workspace

COPY apps/shared-platform/package.json ./apps/shared-platform/package.json
RUN cd apps/shared-platform && npm install --include=dev --no-audit --no-fund

COPY apps/shared-platform ./apps/shared-platform
COPY architecture ./architecture
COPY vendor/florah-demand ./vendor/florah-demand
COPY vendor/customer-engagement-shared ./vendor/customer-engagement-shared

RUN cd apps/shared-platform \
    && npm run check \
    && npm run build \
    && npm run validate:process

FROM node:22-bookworm-slim AS runtime
ENV NODE_ENV=production \
    PORT=8080 \
    PROCESSING_PYTHON=/opt/venv/bin/python \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/apps/shared-platform
COPY apps/shared-platform/package.json ./package.json
RUN npm install --omit=dev --no-audit --no-fund

COPY --from=builder /workspace/apps/shared-platform/server ./server
COPY --from=builder /workspace/apps/shared-platform/dist ./dist
COPY --from=builder /workspace/apps/shared-platform/architecture ./architecture
COPY --from=builder /workspace/apps/shared-platform/data-templates ./data-templates
COPY --from=builder /workspace/apps/shared-platform/docs ./docs
COPY --from=builder /workspace/architecture /workspace/architecture
COPY --from=builder /workspace/vendor/florah-demand /workspace/vendor/florah-demand
COPY --from=builder /workspace/vendor/customer-engagement-shared /workspace/vendor/customer-engagement-shared

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r /workspace/vendor/florah-demand/backend/requirements.txt

WORKDIR /workspace
EXPOSE 8080
CMD ["node", "apps/shared-platform/server/index.mjs"]
