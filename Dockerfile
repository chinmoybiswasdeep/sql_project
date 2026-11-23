FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY config ./config
COPY ingestion ./ingestion
COPY analytics ./analytics
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
# Restricted data is never baked into the image: data/ is mounted at runtime
# and excluded by .dockerignore.
