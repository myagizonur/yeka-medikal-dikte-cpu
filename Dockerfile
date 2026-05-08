FROM python:3.11-slim

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bağımlılıkları önce kopyala (cache için)
COPY requirements.txt .
RUN pip install --no-cache-dir \
    faster-whisper \
    flask \
    flask-socketio \
    flask-cors \
    reportlab \
    python-dotenv \
    requests

# Uygulama dosyaları
COPY . .

EXPOSE 5050

CMD ["python3", "app.py"]
