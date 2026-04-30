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

# Copy sub-packages
COPY directory/ ./directory/
COPY deepthi_intelligence/ ./deepthi_intelligence/
COPY month1_research/ ./month1_research/
COPY month3_systems/ ./month3_systems/
COPY growth/ ./growth/
COPY dynamo/ ./dynamo/

# Copy HTML dashboards & templates
COPY *.html ./
COPY templates/ ./templates/
COPY s3-pages/ ./s3-pages/

# Copy static assets
COPY assets/ ./assets/
COPY static/ ./static/

# Copy config files
COPY apprunner.yaml .
COPY .ebextensions/ ./.ebextensions/

EXPOSE 8080

CMD ["gunicorn", "application:application", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "120"]
