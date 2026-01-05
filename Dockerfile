FROM python:3.10-slim

# Install dependencies and build tools
RUN apt-get update && apt-get install -y \
    aria2 \
    ffmpeg \
    curl \
    lsof \
    net-tools \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . .

# Set ownership and permissions
RUN chmod +x start.sh && \
    mkdir -p downloads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 6801 8000

# Use ENTRYPOINT for better signal handling (allows graceful shutdown)
ENTRYPOINT ["./start.sh"]
