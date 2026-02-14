FROM python:3.13-slim

WORKDIR /app

# umbrella_schema lives in connector-framework
COPY connectors/connector-framework /app/connector-framework

# UI backend
COPY ui/backend /app/ui-backend

RUN pip install --no-cache-dir /app/connector-framework /app/ui-backend

CMD ["python", "-m", "umbrella_ui"]
