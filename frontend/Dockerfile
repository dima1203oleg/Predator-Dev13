# Multi-stage build for Predator Analytics Frontend
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy source code
COPY frontend/ ./

# Build React app
ENV NODE_ENV=production \
    REACT_APP_API_URL=/api \
    REACT_APP_WS_URL=/ws

RUN npm run build

# Runtime stage with nginx
FROM nginx:1.25-alpine AS runtime

# Install curl for healthcheck
RUN apk add --no-cache curl

# Copy custom nginx config
COPY frontend/nginx.conf /etc/nginx/nginx.conf

# Copy built React app from builder
COPY --from=builder /app/build /usr/share/nginx/html

# Create non-root user (nginx runs as nginx user by default in alpine)
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chown -R nginx:nginx /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

USER nginx

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
