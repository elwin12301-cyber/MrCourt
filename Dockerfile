# One container: the React website is built, then served by the FastAPI app at the same address.

FROM node:20-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

FROM python:3.12-slim
# Tesseract reads scanned PDFs (English and Tamil) for the knowledge base.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-tam \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY backend/src ./src
RUN pip install --no-cache-dir .
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY --from=web /web/dist /app/frontend/dist

ENV ENVIRONMENT=production \
    FRONTEND_DIST=/app/frontend/dist \
    COOKIE_SECURE=true \
    PYTHONUNBUFFERED=1 \
    PORT=8000
RUN useradd --create-home mrcourt && mkdir -p /app/backend/uploads && chown -R mrcourt /app/backend
USER mrcourt
EXPOSE 8000
CMD alembic upgrade head && python -m mrcourt.bootstrap && exec uvicorn mrcourt.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'
