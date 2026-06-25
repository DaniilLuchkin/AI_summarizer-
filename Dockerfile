# Telegram LLM bot — Railway worker (no public port, long polling).
FROM python:3.12-slim

# ffmpeg/ffprobe are required for audio extraction and segmentation.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Don't buffer stdout/stderr so logs show up immediately in Railway.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first to leverage Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY bot ./bot

# Runs as a worker; no EXPOSE needed (long polling, outbound only).
CMD ["python", "-m", "bot.main"]
