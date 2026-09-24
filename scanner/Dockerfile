# ===== Scanner image (multi-stage) =====
# This image runs static-analysis tools inside a locked-down container.
# The scanner_runner entrypoint coordinates tool execution and writes
# signals.json + secret_spans.json + tool_logs/ to the output mount.

FROM python:3.12-slim AS builder

# Install all scanner tool dependencies at build time
RUN pip install --no-cache-dir --prefix=/install \
    semgrep bandit gitleaks osv-scanner lizard radon

FROM python:3.12-slim

COPY --from=builder /install /usr/local

# Create non-root scanner user
RUN groupadd -r skillissue-scanner \
    && useradd -r -g skillissue-scanner -d /home/scanner -s /sbin/nologin scanner \
    && mkdir -p /home/scanner /out \
    && chown -R scanner:skillissue-scanner /home/scanner /out

USER scanner
ENV HOME=/home/scanner

COPY scanner/scanner_runner/ /app/scanner_runner/
WORKDIR /app

# Runs scanner_runner which reads from /work/src and writes to /out
ENTRYPOINT ["python", "-m", "scanner_runner"]
