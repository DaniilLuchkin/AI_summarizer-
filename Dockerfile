# Telegram LLM bot — Railway worker (no public port, long polling).
FROM python:3.12-slim

# System deps:
#   ffmpeg            -> audio extraction + segmentation for transcription
#   fonts-dejavu-core -> Unicode TTF so generated PDFs render Cyrillic correctly
#   libreoffice + poppler-utils -> render decks to images for visual QA
#     (soffice --convert-to pdf, then pdftoppm). Materially larger image/build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg fonts-dejavu-core libreoffice-impress poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Don't buffer stdout/stderr so logs show up immediately in Railway.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first to leverage Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code + the idempotent DB schema (read at startup).
COPY bot ./bot
COPY schema.sql ./schema.sql

# Runs as a worker; no EXPOSE needed (long polling, outbound only).
CMD ["python", "-m", "bot.main"]
