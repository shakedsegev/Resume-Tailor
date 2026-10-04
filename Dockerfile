# Production Dockerfile for Resume-Tailor
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    CHROME_PATH=/usr/bin/chromium \
    PORT=10000

# Install Chromium, fonts for international script support (Hebrew, Arabic, CJK, Latin), and LibreOffice for PPTX
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    fonts-noto-core \
    fonts-noto-cjk \
    fonts-noto-extra \
    fonts-freefont-ttf \
    libreoffice-impress \
    libreoffice-writer \
    default-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency specifications
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure outputs and data directories exist
RUN mkdir -p /app/data /app/outputs

# Expose default port
EXPOSE 10000

# Run FastAPI via uvicorn
CMD ["sh", "-c", "uvicorn src.web_app:app --host 0.0.0.0 --port ${PORT:-10000}"]
