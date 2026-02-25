FROM python:3.13-slim

WORKDIR /app

COPY agents /app/agents

RUN pip install --no-cache-dir /app/agents

CMD ["python", "-m", "umbrella_agents"]
