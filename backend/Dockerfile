FROM python:3.12-slim

WORKDIR /app

# Install system deps for Playwright + psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps || true

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
