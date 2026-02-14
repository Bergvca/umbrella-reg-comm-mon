# Phase 4.5 — UI Layer K8s Deployment + Pipeline Test Integration

## Goal

Containerise the UI backend and frontend, deploy them to the `umbrella-ui` namespace in minikube, and extend the existing `test-pipeline-minikube.sh` script to add a **Stage 5** check that verifies end-to-end: login via the deployed UI API → search for the test message → confirm the response.

At the end of this phase the full pipeline — including the UI layer — runs entirely inside minikube, and the test script validates all five stages.

---

## What changes

| Area | Change |
|---|---|
| `ui/backend/Dockerfile` | New — builds the FastAPI backend image |
| `ui/frontend/Dockerfile` | New — multi-stage nginx image serving the React SPA |
| `ui/frontend/nginx.conf` | New — serves static files, proxies `/api` to backend |
| `deploy/k8s/umbrella-ui/` | New directory — all K8s manifests for the UI layer |
| `scripts/build-images.sh` | Add `ui-backend` and `ui-frontend` targets |
| `scripts/test-pipeline-minikube.sh` | Replace the local `uv run` Stage 5 with a deployed K8s Stage 5 + add Stage 6 (login → dashboard) |

---

## 1. Dockerfiles

### 1.1 `ui/backend/Dockerfile`

Follows the same pattern as `connectors/email/Dockerfile` and `ingestion-api/Dockerfile` — builds from repo root, copies the connector-framework (for `umbrella_schema`) and the backend package.

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# umbrella_schema lives in connector-framework
COPY connectors/connector-framework /app/connector-framework

# UI backend
COPY ui/backend /app/ui-backend

RUN pip install --no-cache-dir /app/connector-framework /app/ui-backend

CMD ["python", "-m", "umbrella_ui"]
```

Build context: **repo root** (same as all other images).

### 1.2 `ui/frontend/Dockerfile`

Multi-stage: Node build → nginx serve.

```dockerfile
# ── Stage 1: Build ────────────────────────────────────
FROM node:22-alpine AS build

WORKDIR /app

COPY ui/frontend/package.json ui/frontend/package-lock.json ./
RUN npm ci

COPY ui/frontend/ .
RUN npm run build

# ── Stage 2: Serve ────────────────────────────────────
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY ui/frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
```

Build context: **repo root** (matches nginx.conf COPY path).

### 1.3 `ui/frontend/nginx.conf`

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Gzip static assets
    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;

    # Cache hashed assets aggressively; don't cache index.html
    location ~* \.(?:js|css|woff2?|png|svg|ico)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Proxy /api to the backend service
    location /api/ {
        proxy_pass http://umbrella-ui-backend.umbrella-ui.svc:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # SPA fallback — all non-asset routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 2. Kubernetes Manifests (`deploy/k8s/umbrella-ui/`)

### Directory layout

```
deploy/k8s/umbrella-ui/
├── namespace.yaml
├── secret.yaml
├── backend/
│   ├── configmap.yaml
│   ├── deployment.yaml
│   └── service.yaml
└── frontend/
    ├── deployment.yaml
    └── service.yaml
```

No ingress — access is via `kubectl port-forward` (same pattern as all other services in this repo). An ingress can be added post-MVP.

---

### 2.1 `namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: umbrella-ui
  labels:
    # Allow this namespace to reach Kafka
    umbrella-kafka-access: "true"
```

The `umbrella-kafka-access: "true"` label is required by the existing `NetworkPolicy` in `umbrella-streaming` that gates access to port 9092.

---

### 2.2 `secret.yaml`

Development credentials only — values match the existing PostgreSQL credentials from `deploy/k8s/umbrella-storage/postgresql/`.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: umbrella-ui-credentials
  namespace: umbrella-ui
type: Opaque
stringData:
  # These match the connection strings in postgresql-credentials configmap
  IAM_DATABASE_URL: "postgresql+asyncpg://iam_rw:changeme-iam@postgresql.umbrella-storage.svc:5432/umbrella"
  POLICY_DATABASE_URL: "postgresql+asyncpg://policy_rw:changeme-policy@postgresql.umbrella-storage.svc:5432/umbrella"
  ALERT_DATABASE_URL: "postgresql+asyncpg://alert_rw:changeme-alert@postgresql.umbrella-storage.svc:5432/umbrella"
  REVIEW_DATABASE_URL: "postgresql+asyncpg://review_rw:changeme-review@postgresql.umbrella-storage.svc:5432/umbrella"
  JWT_SECRET: "umbrella-dev-jwt-secret-change-in-production"
```

---

### 2.3 `backend/configmap.yaml`

Non-secret environment variables.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: umbrella-ui-backend-config
  namespace: umbrella-ui
data:
  UMBRELLA_UI_ELASTICSEARCH_URL: "http://elasticsearch.umbrella-storage.svc:9200"
  UMBRELLA_UI_S3_ENDPOINT_URL: "http://minio.umbrella-storage.svc:9000"
  UMBRELLA_UI_S3_BUCKET: "umbrella"
  UMBRELLA_UI_S3_REGION: "us-east-1"
  UMBRELLA_UI_HOST: "0.0.0.0"
  UMBRELLA_UI_PORT: "8000"
  UMBRELLA_UI_LOG_LEVEL: "INFO"
  UMBRELLA_UI_LOG_JSON: "true"
  AWS_ACCESS_KEY_ID: "minioadmin"
  AWS_SECRET_ACCESS_KEY: "minioadmin"
```

---

### 2.4 `backend/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: umbrella-ui-backend
  namespace: umbrella-ui
  labels:
    app: umbrella-ui-backend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: umbrella-ui-backend
  template:
    metadata:
      labels:
        app: umbrella-ui-backend
    spec:
      containers:
        - name: umbrella-ui-backend
          image: umbrella-ui-backend:latest
          imagePullPolicy: Never
          ports:
            - containerPort: 8000
              name: http
          envFrom:
            - configMapRef:
                name: umbrella-ui-backend-config
          env:
            - name: UMBRELLA_UI_IAM_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: umbrella-ui-credentials
                  key: IAM_DATABASE_URL
            - name: UMBRELLA_UI_POLICY_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: umbrella-ui-credentials
                  key: POLICY_DATABASE_URL
            - name: UMBRELLA_UI_ALERT_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: umbrella-ui-credentials
                  key: ALERT_DATABASE_URL
            - name: UMBRELLA_UI_REVIEW_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: umbrella-ui-credentials
                  key: REVIEW_DATABASE_URL
            - name: UMBRELLA_UI_JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: umbrella-ui-credentials
                  key: JWT_SECRET
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 12
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 512Mi
```

`imagePullPolicy: Never` — matches all other local images in this repo.

---

### 2.5 `backend/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: umbrella-ui-backend
  namespace: umbrella-ui
  labels:
    app: umbrella-ui-backend
spec:
  selector:
    app: umbrella-ui-backend
  ports:
    - name: http
      port: 8000
      targetPort: 8000
  type: ClusterIP
```

---

### 2.6 `frontend/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: umbrella-ui-frontend
  namespace: umbrella-ui
  labels:
    app: umbrella-ui-frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: umbrella-ui-frontend
  template:
    metadata:
      labels:
        app: umbrella-ui-frontend
    spec:
      containers:
        - name: umbrella-ui-frontend
          image: umbrella-ui-frontend:latest
          imagePullPolicy: Never
          ports:
            - containerPort: 80
              name: http
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 5
            failureThreshold: 6
          resources:
            requests:
              cpu: 100m
              memory: 64Mi
            limits:
              cpu: 250m
              memory: 128Mi
```

---

### 2.7 `frontend/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: umbrella-ui-frontend
  namespace: umbrella-ui
  labels:
    app: umbrella-ui-frontend
spec:
  selector:
    app: umbrella-ui-frontend
  ports:
    - name: http
      port: 80
      targetPort: 80
  type: ClusterIP
```

---

## 3. `scripts/build-images.sh` — Add UI targets

Extend the existing script with two new image targets: `ui-backend` and `ui-frontend`.

**Changes to `scripts/build-images.sh`:**

1. Add `ui-backend` and `ui-frontend` cases to the argument parser.
2. Update `BUILD_ALL` to include both new images.
3. Add build calls at the bottom.
4. Update the final `docker images` grep to also match `umbrella-ui-*`.

The new `build_image` calls at the bottom:

```bash
if [ "$BUILD_ALL" = true ] || [ "$BUILD_UI_BACKEND" = true ]; then
    build_image "umbrella-ui-backend" "ui/backend/Dockerfile"
fi

if [ "$BUILD_ALL" = true ] || [ "$BUILD_UI_FRONTEND" = true ]; then
    build_image "umbrella-ui-frontend" "ui/frontend/Dockerfile"
fi
```

Updated `docker images` grep:

```bash
docker images | grep -E "umbrella-(email|ingestion|ui-)" | head -20
```

Updated usage message:

```bash
echo "Usage: $0 [email|ingestion|ui-backend|ui-frontend|all]"
```

---

## 4. `scripts/test-pipeline-minikube.sh` — Stage 5 and 6 overhaul

### What changes

The current Stage 5 runs the UI backend **locally** with `uv run`, pointed at a port-forwarded ES. This Phase replaces that with:

- **Stage 5** — same assertion (UI API `/messages/search` returns the test message), but now against the **deployed K8s backend** rather than a local process.
- **Stage 6** — new assertion: `POST /api/v1/auth/login` with the seeded admin user → confirm a JWT is returned → confirm `GET /api/v1/auth/me` returns the expected roles.

Stage 6 validates that PostgreSQL is reachable from the backend and that the V6 seed data (roles, admin user) is present.

### Seeded user for Stage 6

The V6 migration seeds roles and decision statuses but does **not** seed a user (that would require a hashed password). We add a small `kubectl run` step (like the SMTP sender pattern) that inserts a test user into PostgreSQL before the UI backend starts.

The test user insertion runs as a one-shot pod using the `postgres:16-alpine` image (already in minikube from the PostgreSQL StatefulSet).

### New/changed sections in the test script

**After ingestion-service deploy (existing), add:**

```bash
# ── Deploy PostgreSQL ──────────────────────────────────────────────────────
# (Already deployed as part of umbrella-storage above, no change needed)

# ── Insert test user for Stage 6 ──────────────────────────────────────────
info "Inserting test user for UI API authentication check..."
kubectl delete pod pg-seed-user -n umbrella-storage --ignore-not-found 2>/dev/null || true
kubectl run pg-seed-user --rm -i --restart=Never \
  --image=postgres:16-alpine \
  -n umbrella-storage \
  --env="PGPASSWORD=changeme" -- \
  psql -h postgresql.umbrella-storage.svc -U umbrella_admin -d umbrella -c "
INSERT INTO iam.users (id, username, email, password_hash, is_active)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  'testadmin',
  'testadmin@umbrella.local',
  '\$2b\$12\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LwGqiK7UNvEdv5q.W',
  true
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO iam.groups (id, name, description)
VALUES ('00000000-0000-0000-0000-000000000010', 'admins', 'Admin group')
ON CONFLICT (id) DO NOTHING;

INSERT INTO iam.user_groups (user_id, group_id)
VALUES ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000010')
ON CONFLICT DO NOTHING;

INSERT INTO iam.group_roles (group_id, role_id)
SELECT '00000000-0000-0000-0000-000000000010', id FROM iam.roles WHERE name = 'admin'
ON CONFLICT DO NOTHING;
"
# Password above is bcrypt of 'testpass123' (12 rounds)
```

**Build UI images (added to Step 3 block):**

```bash
info "Building UI images..."
docker build --no-cache -f ui/backend/Dockerfile -t umbrella-ui-backend:latest .
docker build --no-cache -f ui/frontend/Dockerfile -t umbrella-ui-frontend:latest .
```

**Deploy UI layer (after ingestion-service deploy):**

```bash
info "Deploying umbrella-ui (backend + frontend)..."
kubectl apply -f deploy/k8s/umbrella-ui/namespace.yaml
kubectl apply -f deploy/k8s/umbrella-ui/secret.yaml
kubectl apply -f deploy/k8s/umbrella-ui/backend/
kubectl apply -f deploy/k8s/umbrella-ui/frontend/

info "Waiting for UI backend to be ready..."
kubectl rollout status deployment/umbrella-ui-backend -n umbrella-ui --timeout=120s

info "Waiting for UI frontend to be ready..."
kubectl rollout status deployment/umbrella-ui-frontend -n umbrella-ui --timeout=60s
```

**Replace the existing Stage 5 block entirely:**

```bash
# ── Stage 5: UI backend message search API (deployed in K8s) ──────────────
info "Checking UI backend message search API (Stage 5)..."
UI_RESULT=0

# Port-forward the deployed backend (not a local process)
kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
PF_UI_PID=$!
sleep 3

# Generate a reviewer JWT using the same secret that's in the K8s secret
TEST_JWT_SECRET="umbrella-dev-jwt-secret-change-in-production"
UI_TOKEN=$(python3 -c "
from jose import jwt
import uuid, time
payload = {
    'sub': '00000000-0000-0000-0000-000000000001',
    'roles': ['reviewer'],
    'type': 'access',
    'exp': int(time.time()) + 300,
}
print(jwt.encode(payload, '$TEST_JWT_SECRET', algorithm='HS256'))
")

API_RESPONSE=$(curl -s -H "Authorization: Bearer $UI_TOKEN" \
    "http://localhost:8001/api/v1/messages/search?q=pipeline-test-001")
UI_RESULT=$(echo "$API_RESPONSE" | jq -r '.total // 0' 2>/dev/null || echo "0")

kill $PF_UI_PID 2>/dev/null || true

if [ "$UI_RESULT" -gt 0 ]; then
    info "✓ UI API returned $UI_RESULT message(s) for the test email"
else
    warn "✗ UI API returned no messages (response: $API_RESPONSE)"
fi

# ── Stage 6: UI login + auth flow (validates PostgreSQL + RBAC) ───────────
info "Checking UI login flow (Stage 6)..."
LOGIN_OK=0

kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000 >/dev/null 2>&1 &
PF_UI2_PID=$!
sleep 2

LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"testadmin","password":"testpass123"}')

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token // empty' 2>/dev/null)

if [ -n "$ACCESS_TOKEN" ] && [ "$ACCESS_TOKEN" != "null" ]; then
    # Confirm /me returns admin role
    ME_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
        http://localhost:8001/api/v1/auth/me)
    HAS_ADMIN=$(echo "$ME_RESPONSE" | jq -r '[.roles[]? | select(. == "admin")] | length' 2>/dev/null || echo "0")

    if [ "$HAS_ADMIN" -gt 0 ]; then
        info "✓ Login succeeded — testadmin has admin role"
        LOGIN_OK=1
    else
        warn "✗ Login succeeded but admin role missing (response: $ME_RESPONSE)"
    fi
else
    warn "✗ Login failed (response: $LOGIN_RESPONSE)"
fi

kill $PF_UI2_PID 2>/dev/null || true
```

**Update the summary block:**

```bash
echo "Stage 1 (IMAP Connector):    $([ "$RAW_COUNT" -gt 0 ]   && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 2 (Email Processor):   $([ "$PARSED_COUNT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 3 (Ingestion Service): $([ "$NORMALIZED_COUNT" -gt 0 ] && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 4 (Logstash → ES):     $([ "$ES_RESULT" -gt 0 ]    && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 5 (UI API search):     $([ "$UI_RESULT" -gt 0 ]    && echo '[✓ PASS]' || echo '[✗ FAIL]')"
echo "Stage 6 (UI login/auth):     $([ "$LOGIN_OK" -eq 1 ]     && echo '[✓ PASS]' || echo '[✗ FAIL]')"
```

**Update the pass/fail condition:**

```bash
if [ "$RAW_COUNT" -gt 0 ] && [ "$PARSED_COUNT" -gt 0 ] && \
   [ "$NORMALIZED_COUNT" -gt 0 ] && [ "$ES_RESULT" -gt 0 ] && \
   [ "$UI_RESULT" -gt 0 ] && [ "$LOGIN_OK" -eq 1 ]; then
```

**Update the success output hints:**

```bash
info "To access the UI:"
echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-frontend 3000:80"
echo "  Open http://localhost:3000 — login with testadmin / testpass123"
echo ""
info "To access the UI API directly:"
echo "  kubectl port-forward -n umbrella-ui svc/umbrella-ui-backend 8001:8000"
echo "  Open http://localhost:8001/docs for the OpenAPI UI"
```

**Update the failure debugging hints:**

```bash
echo "  kubectl logs -n umbrella-ui -l app=umbrella-ui-backend --tail=50"
echo "  kubectl logs -n umbrella-ui -l app=umbrella-ui-frontend --tail=50"
```

---

## 5. Implementation Order

| Step | What | Files |
|------|------|-------|
| **1** | Write `ui/backend/Dockerfile` | `ui/backend/Dockerfile` |
| **2** | Write `ui/frontend/nginx.conf` | `ui/frontend/nginx.conf` |
| **3** | Write `ui/frontend/Dockerfile` | `ui/frontend/Dockerfile` |
| **4** | Write K8s namespace | `deploy/k8s/umbrella-ui/namespace.yaml` |
| **5** | Write K8s secret | `deploy/k8s/umbrella-ui/secret.yaml` |
| **6** | Write backend configmap | `deploy/k8s/umbrella-ui/backend/configmap.yaml` |
| **7** | Write backend deployment | `deploy/k8s/umbrella-ui/backend/deployment.yaml` |
| **8** | Write backend service | `deploy/k8s/umbrella-ui/backend/service.yaml` |
| **9** | Write frontend deployment | `deploy/k8s/umbrella-ui/frontend/deployment.yaml` |
| **10** | Write frontend service | `deploy/k8s/umbrella-ui/frontend/service.yaml` |
| **11** | Update `build-images.sh` | `scripts/build-images.sh` |
| **12** | Update test script | `scripts/test-pipeline-minikube.sh` |

---

## 6. minikube Resource Impact

| Component | CPU Request | Memory Request |
|---|---|---|
| UI Backend | 250m | 256Mi |
| UI Frontend | 100m | 64Mi |
| **Added** | **+350m** | **+320Mi** |

Total cluster: ~2.5 CPU request, ~5.8Gi memory request — stays comfortably within `--memory=8192 --cpus=4`.

---

## 7. Acceptance Criteria

Phase 4.5 is complete when:

- [ ] `docker build -f ui/backend/Dockerfile -t umbrella-ui-backend:latest .` succeeds from repo root
- [ ] `docker build -f ui/frontend/Dockerfile -t umbrella-ui-frontend:latest .` succeeds from repo root
- [ ] `kubectl apply -f deploy/k8s/umbrella-ui/` creates all resources without errors
- [ ] `kubectl rollout status deployment/umbrella-ui-backend -n umbrella-ui` reports success
- [ ] `kubectl rollout status deployment/umbrella-ui-frontend -n umbrella-ui` reports success
- [ ] Port-forwarding backend (`:8001`) and hitting `/health` returns `{"status":"ok"}`
- [ ] Port-forwarding backend and hitting `/api/v1/auth/login` with `testadmin`/`testpass123` returns a JWT
- [ ] Port-forwarding frontend (`:3000`) and opening a browser shows the Umbrella login page
- [ ] `scripts/build-images.sh all` builds all four images (email, ingestion, ui-backend, ui-frontend)
- [ ] `scripts/test-pipeline-minikube.sh` passes all six stages

---

## 8. Non-Goals (Deferred)

- Ingress / external DNS — access via port-forward is sufficient for minikube
- TLS — HTTP only in the dev cluster
- HPA — fixed replicas in minikube
- Production secrets management (Vault, Sealed Secrets, External Secrets)
- Prometheus/Grafana dashboards for the UI layer
