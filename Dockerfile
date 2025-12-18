FROM python:3.12-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    aria2 \
    ffmpeg \
    curl \
    lsof \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . .

# Permissions
RUN chmod +x start.sh && \
    mkdir -p downloads && \
    chown -R 1000:1000 downloads

# Expose ports
EXPOSE 6801 8000

CMD ["./start.sh"]
