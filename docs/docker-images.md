# Docker Images

This document describes the Docker images for Umbrella Python services.

## Architecture

All Python services depend on the `umbrella-connector-framework` package as a local dependency. Therefore:

- **Build context must be the repository root**
- Dockerfiles copy both the framework and the service code
- Images are built from the root using `-f <path/to/Dockerfile>`

## Available Images

### 1. umbrella-email

**Location**: `connectors/email/Dockerfile`

**Contains**:
- Email connector (Stage 1: IMAP → S3 + Kafka)
- Email processor (Stage 2: Kafka → parse → Kafka)

**Entry points** (override CMD in K8s):
```bash
# Stage 1: IMAP connector
python -m umbrella_email connector

# Stage 2: Email processor (default)
python -m umbrella_email processor
```

**Dependencies**:
- `umbrella-connector-framework`
- `boto3` (S3 access)

### 2. umbrella-ingestion

**Location**: `ingestion-api/Dockerfile`

**Contains**:
- Ingestion/normalization service (Stage 3: parsed → normalized)

**Entry point**:
```bash
python -m umbrella_ingestion
```

**Dependencies**:
- `umbrella-connector-framework`
- `boto3` (S3 access)

## Building Images

### Quick Build (all services)

```bash
./scripts/build-images.sh
```

### Build Individual Services

```bash
# Email connector/processor
./scripts/build-images.sh email

# Ingestion service
./scripts/build-images.sh ingestion
```

### Manual Build

```bash
# Email connector/processor
docker build -t umbrella-email:latest -f connectors/email/Dockerfile .

# Ingestion service
docker build -t umbrella-ingestion:latest -f ingestion-api/Dockerfile .
```

**Important**: Always build from the repository root (`.`), not from the service directory.

## Building for Minikube

When deploying to minikube, build images in minikube's Docker daemon:

```bash
# Point Docker CLI to minikube's daemon
eval $(minikube docker-env)

# Build images (they'll be available in minikube)
./scripts/build-images.sh

# Verify
minikube image ls | grep umbrella
```

## Building for Remote Registry

```bash
# Set registry and tag
export DOCKER_REGISTRY=my-registry.io/umbrella
export IMAGE_TAG=v0.1.0

# Build and tag
./scripts/build-images.sh

# Push to registry
docker push my-registry.io/umbrella/umbrella-email:v0.1.0
docker push my-registry.io/umbrella/umbrella-ingestion:v0.1.0
```

## Image Contents

### Base Image
- `python:3.13-slim` (Debian-based, minimal)

### Installed Packages
- `umbrella-connector-framework` (from `/app/connector-framework`)
- Service-specific package (from `/app/email-connector` or `/app/ingestion`)
- All transitive dependencies (aiokafka, structlog, pydantic, httpx, boto3, etc.)

### Working Directory
- `/app`

## Size Optimization

The `.dockerignore` file at the repository root excludes:
- Test files
- Documentation (except README)
- `.git` directory
- Virtual environments
- Python caches
- IDE configurations
- Infrastructure manifests

Typical image sizes:
- **umbrella-email**: ~200-300 MB
- **umbrella-ingestion**: ~200-300 MB

## Troubleshooting

### "No such file or directory" during build

**Cause**: Building from the wrong directory.

**Solution**: Always build from the repository root:
```bash
cd /path/to/regcommon
docker build -t umbrella-email:latest -f connectors/email/Dockerfile .
#                                                                   ^ note the dot
```

### "Could not find umbrella-connector-framework"

**Cause**: The connector-framework wasn't copied or installed correctly.

**Solution**: Verify the COPY commands in the Dockerfile include both packages.

### Image works locally but fails in K8s

**Cause**: Image might not be available in the cluster.

**Solutions**:
- For minikube: Use `eval $(minikube docker-env)` before building
- For remote clusters: Push to a registry and use `imagePullPolicy: Always`

## Multi-stage Build (Future Optimization)

For production, consider multi-stage builds:

```dockerfile
# Build stage
FROM python:3.13-slim AS builder
WORKDIR /app
COPY connectors/connector-framework /app/connector-framework
COPY connectors/email /app/email-connector
RUN pip install --no-cache-dir --target=/install /app/connector-framework /app/email-connector

# Runtime stage
FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /install /usr/local/lib/python3.13/site-packages
CMD ["python", "-m", "umbrella_email", "processor"]
```

This can reduce image size by ~30-40%.
