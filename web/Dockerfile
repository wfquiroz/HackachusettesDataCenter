# HourMatch map — Node + Express serving a Leaflet frontend
FROM node:20-alpine

WORKDIR /app

# Install dependencies first (better layer caching).
# Include dev deps so nodemon is available for auto-restart in dev.
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest of the app
COPY server.js ./
COPY facilities.json ./
COPY layers.json ./
COPY surfaces.json ./
COPY public ./public

ENV PORT=5173
EXPOSE 5173

# Lightweight healthcheck
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -qO- http://127.0.0.1:5173/healthz || exit 1

# Run via nodemon so edits to server.js / data files auto-restart the server.
# Static files (public/) are served live and need no restart.
CMD ["npm", "run", "dev"]
