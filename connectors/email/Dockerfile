FROM python:3.13-slim

WORKDIR /app

# Copy connector framework (local dependency)
COPY connectors/connector-framework /app/connector-framework

# Copy email connector source
COPY connectors/email /app/email-connector

# Install both packages in editable mode for faster rebuilds during dev
RUN pip install --no-cache-dir /app/connector-framework /app/email-connector

# Default command (can be overridden in K8s manifests)
# Options: "connector" (Stage 1: IMAP → Kafka) or "processor" (Stage 2: Kafka → parse → Kafka)
CMD ["python", "-m", "umbrella_email", "processor"]
