#!/usr/bin/env bash
# Validate Docker setup for Umbrella services
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "Validating Docker Setup"
echo "=========================================="
echo ""

# Check if required files exist
check_file() {
    local file=$1
    if [ -f "$file" ]; then
        echo "✓ $file exists"
        return 0
    else
        echo "✗ $file missing"
        return 1
    fi
}

# Check if required directories exist
check_dir() {
    local dir=$1
    if [ -d "$dir" ]; then
        echo "✓ $dir exists"
        return 0
    else
        echo "✗ $dir missing"
        return 1
    fi
}

echo "Checking Dockerfiles..."
check_file "connectors/email/Dockerfile"
check_file "ingestion-api/Dockerfile"
check_file ".dockerignore"
echo ""

echo "Checking source packages..."
check_dir "connectors/connector-framework/umbrella_connector"
check_dir "connectors/email/umbrella_email"
check_dir "ingestion-api/umbrella_ingestion"
check_file "connectors/connector-framework/pyproject.toml"
check_file "connectors/email/pyproject.toml"
check_file "ingestion-api/pyproject.toml"
echo ""

echo "Validating Dockerfile structure..."

# Check that Dockerfiles use correct COPY paths (relative to root)
validate_dockerfile() {
    local dockerfile=$1
    local name=$2

    echo "  Validating $name..."

    if ! grep -q "^COPY connectors/connector-framework" "$dockerfile"; then
        echo "    ✗ Missing connector-framework COPY"
        return 1
    fi
    echo "    ✓ Copies connector-framework"

    if ! grep -q "^FROM python:3.13-slim" "$dockerfile"; then
        echo "    ✗ Not using python:3.13-slim"
        return 1
    fi
    echo "    ✓ Uses python:3.13-slim base image"

    if ! grep -q "^WORKDIR /app" "$dockerfile"; then
        echo "    ✗ Missing WORKDIR /app"
        return 1
    fi
    echo "    ✓ Sets WORKDIR to /app"

    if ! grep -q "^CMD" "$dockerfile"; then
        echo "    ✗ Missing CMD"
        return 1
    fi
    echo "    ✓ Has CMD directive"

    return 0
}

validate_dockerfile "connectors/email/Dockerfile" "email-connector"
echo ""
validate_dockerfile "ingestion-api/Dockerfile" "ingestion-service"
echo ""

echo "Checking if Docker is available..."
if command -v docker &> /dev/null; then
    echo "✓ Docker is installed"
    docker --version
else
    echo "✗ Docker not found in PATH"
    echo "  Install Docker to build images"
fi
echo ""

echo "=========================================="
echo "Validation Complete!"
echo "=========================================="
echo ""
echo "To build images:"
echo "  ./scripts/build-images.sh"
echo ""
echo "For minikube deployment:"
echo "  eval \$(minikube docker-env)"
echo "  ./scripts/build-images.sh"
