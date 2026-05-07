FROM python:3.12-bookworm

WORKDIR /app

# Install system deps for Playwright + psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps || true

# Copy backend code into /app/backend so "from backend.xxx" imports work
COPY . ./backend/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Railway / Cloud: start the API server
# PORT is injected by Railway automatically
CMD ["/bin/sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
