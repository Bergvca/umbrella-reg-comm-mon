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
