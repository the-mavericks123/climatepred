# Multi-stage production-hardened Dockerfile for God's Eye View (GEV) Frontend
FROM node:20-alpine AS builder

WORKDIR /build

COPY gods-eye-view/package.json gods-eye-view/package-lock.json* ./
RUN npm ci --ignore-scripts

COPY gods-eye-view/ ./
RUN npm run build

# Nginx Alpine Runtime Stage
FROM nginx:1.25-alpine AS runner

# Security: Remove default Nginx HTML
RUN rm -rf /usr/share/nginx/html/*

# Copy built static artifacts
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
