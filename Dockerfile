# Use Python 3.12 slim as base image
# FROM docker.arvancloud.ir/python:3.12-slim
FROM docker.roshan-ai.ir/python:3.10


ENV JAVA_OPTS="-Xmx512m"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies and security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    curl \
    wget \
    nmap \
    ruby \
    ruby-dev \
    whatweb \
    openjdk-17-jre-headless \
    ca-certificates \
    python3-dev \
    # Dependencies for Nikto
    perl \
    libnet-ssleay-perl \
    # zaproxy \
    && rm -rf /var/lib/apt/lists/*

# Install OWASP ZAP
ARG ZAP_VERSION=2.17.0

RUN wget -O /tmp/ZAP.tar.gz \
    https://github.com/zaproxy/zaproxy/releases/download/v${ZAP_VERSION}/ZAP_${ZAP_VERSION}_Linux.tar.gz && \
    tar -xzf /tmp/ZAP.tar.gz -C /opt && \
    rm /tmp/ZAP.tar.gz && \
    ln -s /opt/ZAP_${ZAP_VERSION}/zap.sh /usr/local/bin/zap

# Install Nikto from source
RUN git clone https://github.com/sullo/nikto.git /opt/nikto && \
    ln -s /opt/nikto/program/nikto.pl /usr/local/bin/nikto && \
    chmod +x /opt/nikto/program/nikto.pl

# Install Wapiti via pip (official recommended method)
RUN pip install --no-cache-dir wapiti3



# Install dirsearch from git
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

# Create directory for wordlist
RUN mkdir -p /app/chat && \
    if [ -f /app/dirsearch-wordlist.txt ]; then \
        cp /app/dirsearch-wordlist.txt /app/chat/dirsearch-wordlist.txt; \
    fi

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]