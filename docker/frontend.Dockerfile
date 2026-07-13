# Frontend image: Vite build → static files served by nginx.
FROM node:20-alpine AS build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
# Same-origin API (Traefik routes /api on the app host to the backend), so no URL bake.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine

COPY docker/nginx/frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/dist /usr/share/nginx/html

HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:80/ || exit 1
