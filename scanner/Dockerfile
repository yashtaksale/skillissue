# ===== Scanner image (multi-stage) =====
# This image runs static-analysis tools inside a locked-down container.
# Per ARCHITECTURE.md §7.3: runs as non-root, no network, read-only /work/src.
# Per MEMORY.md D-002: Semgrep dropped; using Bandit + ESLint + gitleaks + OSV + Lizard + Radon.

# Pin base images by version for reproducibility and security
FROM python:3.12-slim AS py-builder

RUN pip install --no-cache-dir --prefix=/install \
    bandit==1.8.3 \
    lizard==1.17.13 \
    radon==6.0.1

# ── Node.js tools ────────────────────────────────────────────────────
FROM node:20-slim AS node-builder

RUN npm install -g \
    eslint@9.27.0 \
    @eslint/js@9.27.0 \
    typescript-eslint@8.32.1 \
    eslint-plugin-security@3.0.1 \
    eslint-plugin-no-unsanitized@4.1.2 \
    globals@16.1.0

# ── gitleaks binary ──────────────────────────────────────────────────
FROM golang:1.23-alpine AS gitleaks-builder

RUN apk add --no-cache git && \
    go install github.com/gitleaks/gitleaks/v8@v8.24.3

# ── OSV-Scanner binary ──────────────────────────────────────────────
FROM golang:1.23-alpine AS osv-builder

RUN apk add --no-cache git && \
    go install github.com/google/osv-scanner/cmd/osv-scanner@v1.9.3

# ── Final scanner image ─────────────────────────────────────────────
FROM python:3.12-slim

# Install Node.js runtime for ESLint
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy Python tools
COPY --from=py-builder /install /usr/local

# Copy Node tools
COPY --from=node-builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node-builder /usr/local/bin/eslint /usr/local/bin/eslint
RUN ln -sf /usr/local/lib/node_modules/eslint/bin/eslint.js /usr/local/bin/eslint || true

# Copy Go binaries
COPY --from=gitleaks-builder /go/bin/gitleaks /usr/local/bin/gitleaks
COPY --from=osv-builder /go/bin/osv-scanner /usr/local/bin/osv-scanner

# Create non-root scanner user
RUN groupadd -r skillissue-scanner \
    && useradd -r -g skillissue-scanner -d /home/scanner -s /sbin/nologin scanner \
    && mkdir -p /home/scanner /out /work/src \
    && chown -R scanner:skillissue-scanner /home/scanner /out

USER scanner
ENV HOME=/home/scanner
ENV PATH="/usr/local/bin:$PATH"

COPY scanner/scanner_runner/ /app/scanner_runner/
COPY scanner/rules/ /app/rules/
WORKDIR /app

# Runs scanner_runner which reads from /work/src and writes to /out
ENTRYPOINT ["python", "-m", "scanner_runner"]
