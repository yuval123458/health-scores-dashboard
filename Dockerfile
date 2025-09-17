FROM node:20-alpine AS webbuild
WORKDIR /work/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build            # -> /work/frontend/dist

FROM python:3.11-slim AS api
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY backend/ ./backend/

COPY --from=webbuild /work/frontend/dist ./frontend/dist

ENV FRONTEND_DIST=/app/frontend/dist
ENV PORT=8080
EXPOSE 8080

CMD exec gunicorn -k uvicorn.workers.UvicornWorker \
    -w 2 -b 0.0.0.0:$PORT backend.api.main:app
