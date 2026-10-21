# One container: builds the React app, then runs Django (API + built web app) with gunicorn.
FROM node:20-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_DEBUG=0
WORKDIR /app
COPY api/requirements.txt api/requirements.txt
COPY engine/requirements.txt engine/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY engine/ engine/
COPY api/ api/
COPY --from=web /web/dist web/dist
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser
WORKDIR /app/api
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60"]
