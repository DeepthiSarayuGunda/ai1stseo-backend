FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY application.py .

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD ["gunicorn", "application:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
