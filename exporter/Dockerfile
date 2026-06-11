FROM python:3.12-slim

# Install ping and snmp tools (removed snmp-mibs-downloader)
RUN apt-get update && apt-get install -y --no-install-recommends \
        iputils-ping \
        snmp \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY exporter.py .

EXPOSE 9200
ENV CONFIG_PATH=/etc/exporter/devices.yaml \
    METRICS_PORT=9200 \
    POLL_INTERVAL=30

CMD ["python", "-u", "exporter.py"]