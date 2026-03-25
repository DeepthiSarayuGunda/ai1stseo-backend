FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY application.py .
COPY bedrock_helper.py .
COPY index.html .
COPY analyze.html .
COPY audit.html .
COPY assets/ ./assets/

EXPOSE 8080

CMD ["gunicorn", "application:application", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "120"]
