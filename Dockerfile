FROM python:3.10-slim

# Install system dependencies for pyzbar (libzbar0) and ffmpeg
RUN apt-get update && apt-get install -y \
    libzbar0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .

CMD ["python", "-m", "backend.run_backend"]
