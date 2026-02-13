#!/usr/bin/env bash
# Build Docker images for Umbrella Python services
set -e

# Get the repository root (parent of scripts dir)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Default registry (can be overridden)
REGISTRY="${DOCKER_REGISTRY:-}"
TAG="${IMAGE_TAG:-latest}"

# Function to build and optionally tag with registry
build_image() {
    local service_name=$1
    local dockerfile_path=$2
    local image_name="${service_name}:${TAG}"

    echo "=========================================="
    echo "Building ${image_name}"
    echo "=========================================="

    # Build from repo root context
    docker build \
        -t "${image_name}" \
        -f "${dockerfile_path}" \
        .

    # Tag with registry if specified
    if [ -n "$REGISTRY" ]; then
        local registry_image="${REGISTRY}/${image_name}"
        echo "Tagging as ${registry_image}"
        docker tag "${image_name}" "${registry_image}"
    fi

    echo "✓ Built ${image_name}"
    echo ""
}

# Parse arguments
BUILD_EMAIL=false
BUILD_INGESTION=false
BUILD_ALL=false

if [ $# -eq 0 ]; then
    BUILD_ALL=true
else
    while [ $# -gt 0 ]; do
        case "$1" in
            email)
                BUILD_EMAIL=true
                ;;
            ingestion)
                BUILD_INGESTION=true
                ;;
            all)
                BUILD_ALL=true
                ;;
            *)
                echo "Unknown service: $1"
                echo "Usage: $0 [email|ingestion|all]"
                echo "  If no argument provided, builds all images"
                exit 1
                ;;
        esac
        shift
    done
fi

# Build requested images
if [ "$BUILD_ALL" = true ] || [ "$BUILD_EMAIL" = true ]; then
    build_image "umbrella-email" "connectors/email/Dockerfile"
fi

if [ "$BUILD_ALL" = true ] || [ "$BUILD_INGESTION" = true ]; then
    build_image "umbrella-ingestion" "ingestion-api/Dockerfile"
fi

echo "=========================================="
echo "All builds completed successfully!"
echo "=========================================="
echo ""
echo "Images built:"
docker images | grep -E "umbrella-(email|ingestion)" | head -10

echo ""
echo "To use with minikube:"
echo "  eval \$(minikube docker-env)"
echo "  $0"
