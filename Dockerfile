# =========================
# Builder Stage
# =========================
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

#  Install deno (static binary from GitHub — NAS safe)
RUN curl -L https://github.com/denoland/deno/releases/download/v2.6.10/deno-x86_64-unknown-linux-gnu.zip -o deno.zip && \
    unzip deno.zip && \
    mv deno /usr/local/bin/deno && \
    chmod +x /usr/local/bin/deno && \
    rm deno.zip

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user
RUN useradd -m appuser

# Prepare directories
RUN mkdir -p /downloads && chown -R appuser:appuser /downloads


# =========================
# Runtime Stage
# =========================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install deno (again for runtime container)
RUN curl -L https://github.com/denoland/deno/releases/download/v2.6.10/deno-x86_64-unknown-linux-gnu.zip -o deno.zip && \
    unzip deno.zip && \
    mv deno /usr/local/bin/deno && \
    chmod +x /usr/local/bin/deno && \
    rm deno.zip

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Non-root user
RUN useradd -m appuser

# Copy application
COPY . .

# Prepare runtime dirs
RUN mkdir -p /downloads /logs && \
    chown -R appuser:appuser /downloads /logs

# Default environment variables
ENV OUTPUT_DIR=/downloads \
    MP3_QUALITY=0 \
    RATE_LIMIT=0 \
    MAX_RETRIES=3 \
    VERBOSE=0 \
    LOG_FILE=/logs/ytm-downloader.log

# Run as non-root
USER appuser

ENTRYPOINT ["python", "main.py"]

CMD ["--help"]
