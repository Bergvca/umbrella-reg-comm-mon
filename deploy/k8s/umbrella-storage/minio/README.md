# MinIO Object Storage

MinIO S3-compatible object storage for the Umbrella platform.

## Components

- **Deployment**: Single-node MinIO server
- **Service**: ClusterIP service exposing API (9000) and Console (9001)
- **PVC**: 5Gi persistent volume for data storage
- **Job**: Initialization job to create the `umbrella` bucket

## Credentials

Default credentials (for development only):
- **Username**: `minioadmin`
- **Password**: `minioadmin`

## Deployment

```bash
# Apply MinIO manifests (namespace must already exist)
kubectl apply -f deploy/k8s/umbrella-storage/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-storage/minio/

# Wait for MinIO to be ready
kubectl rollout status deployment/minio -n umbrella-storage

# Verify bucket creation job completed
kubectl get jobs -n umbrella-storage
kubectl logs job/minio-create-bucket -n umbrella-storage
```

## Accessing MinIO

### From within the cluster:
- **API endpoint**: `http://minio.umbrella-storage.svc:9000`
- **Console**: `http://minio.umbrella-storage.svc:9001`

### From outside (port-forward):
```bash
# API
kubectl port-forward -n umbrella-storage svc/minio 9000:9000

# Console
kubectl port-forward -n umbrella-storage svc/minio 9001:9001
```

## Configuration for Python Services

Services should use these environment variables:

```bash
S3_BUCKET=umbrella
S3_ENDPOINT_URL=http://minio.umbrella-storage.svc:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
```

## Resources

- **Requests**: 256Mi memory, 100m CPU
- **Limits**: 512Mi memory, 500m CPU
- **Storage**: 5Gi PVC

## Health Checks

- **Liveness**: `/minio/health/live` on port 9000
- **Readiness**: `/minio/health/ready` on port 9000
