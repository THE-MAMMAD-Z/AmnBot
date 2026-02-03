# Use Python 3.12 slim as base image
# FROM docker.arvancloud.ir/python:3.12-slim
FROM docker.roshan-ai.ir/python:3.10

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies and security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials for compiling tools
    build-essential \
    gcc \
    git \
    curl \
    wget \
    # Network tools
    nmap \
    # Ruby for whatweb
    ruby \
    ruby-dev \
    whatweb \
    # Go for nuclei (will install latest Go)
    ca-certificates \
    # Python dependencies
    python3-dev \
    && rm -rf /var/lib/apt/lists/*


# # Install dirsearch from git
RUN git clone https://github.com/maurosoria/dirsearch.git /opt/dirsearch && \
    cd /opt/dirsearch && \
    pip install --no-cache-dir -r requirements.txt && \
    chmod +x /opt/dirsearch/dirsearch.py && \
    echo '#!/bin/sh\npython3 /opt/dirsearch/dirsearch.py "$@"' > /usr/local/bin/dirsearch && \
    chmod +x /usr/local/bin/dirsearch

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create directory for wordlist if needed
RUN mkdir -p /app/chat && \
    if [ -f /app/dirsearch-wordlist.txt ]; then \
        cp /app/dirsearch-wordlist.txt /app/chat/wordlist.txt; \
    fi

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]

