FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY PHI/requirements.txt .
# Pre-install build deps for openai-whisper (needs old setuptools with pkg_resources)
RUN pip install --no-cache-dir "setuptools<70" wheel numpy==1.26.2
# Install openai-whisper using system packages (no build isolation)
RUN pip install --no-cache-dir --no-build-isolation openai-whisper==20231117
# Install remaining deps (already installed ones will be skipped)
RUN pip install --no-cache-dir -r requirements.txt

COPY PHI/ .

ENV PORT=8000

EXPOSE $PORT
CMD uvicorn minimal_server:app --host 0.0.0.0 --port $PORT
