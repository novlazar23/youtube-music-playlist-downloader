# =========================
# Builder Stage
# =========================
FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Deno ONCE
RUN curl -L https://github.com/denoland/deno/releases/download/v2.6.10/deno-x86_64-unknown-linux-gnu.zip -o deno.zip && \
    unzip deno.zip && \
    mv deno /usr/local/bin/deno && \
    chmod +x /usr/local/bin/deno && \
    rm deno.zip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -m appuser
RUN mkdir -p /downloads && chown -R appuser:appuser /downloads


# =========================
# Runtime Stage
# =========================
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy deno from builder (NO NETWORK)
COPY --from=builder /usr/local/bin/deno /usr/local/bin/deno

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

RUN useradd -m appuser
COPY . .

RUN mkdir -p /downloads /logs && \
    chown -R appuser:appuser /downloads /logs

ENV OUTPUT_DIR=/downloads \
    MP3_QUALITY=0 \
    RATE_LIMIT=0 \
    MAX_RETRIES=3 \
    VERBOSE=0 \
    LOG_FILE=/logs/ytm-downloader.log

USER appuser

ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
