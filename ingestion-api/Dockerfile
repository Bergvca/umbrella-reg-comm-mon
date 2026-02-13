FROM python:3.13-slim

WORKDIR /app

# Copy connector framework (local dependency)
COPY connectors/connector-framework /app/connector-framework

# Copy ingestion service source
COPY ingestion-api /app/ingestion

# Install both packages
RUN pip install --no-cache-dir /app/connector-framework /app/ingestion

# Run the ingestion/normalization service
CMD ["python", "-m", "umbrella_ingestion"]
