# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM node:22-slim AS builder
WORKDIR /app

# Build-time env vars (Vite bakes VITE_* at compile time)
ARG VITE_PLAUSIBLE_DOMAIN
ARG VITE_TURNSTILE_SITE_KEY
ENV VITE_PLAUSIBLE_DOMAIN=$VITE_PLAUSIBLE_DOMAIN
ENV VITE_TURNSTILE_SITE_KEY=$VITE_TURNSTILE_SITE_KEY

COPY package*.json ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

# ── Stage 2: serve ──────────────────────────────────────────────────────────
# Nginx serves the pre-built static files.  The /api proxy is handled by the
# outer nginx reverse-proxy service in docker-compose.yml.
FROM nginx:1.27-alpine AS runner

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy the Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA nginx config — serve index.html fallback for client-side routing
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
