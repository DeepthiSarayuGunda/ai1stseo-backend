FROM python:3.13-slim

WORKDIR /app

# Install system deps for psycopg2 (in case binary wheel fails)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Python modules
COPY *.py ./

# Copy HTML dashboards
COPY *.html ./

# Copy static assets
COPY assets/ ./assets/

# Copy config files
COPY apprunner.yaml .

EXPOSE 8080

CMD ["gunicorn", "application:application", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "120"]
