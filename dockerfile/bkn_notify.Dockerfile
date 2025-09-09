# Dockerfile para bkn_notify (FastAPI)
# dockerfile/bkn_notify.Dockerfile
FROM python:3.11-slim

LABEL maintainer="notify-stack"
LABEL service="bkn_notify"
LABEL version="1.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Usuario no-root
RUN groupadd -r notify && useradd -r -g notify notify

# Directorio de trabajo: apunta al código
WORKDIR /app

# Instalar deps Python
COPY Stacks/bkn_notify/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código y configs
COPY Stacks/bkn_notify/ .
COPY Config/ ./Config/

# Crear dirs útiles
RUN mkdir -p logs templates && chown -R notify:notify /app

USER notify
EXPOSE 8000

# Healthcheck de la API
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/api/healthz')" || exit 1

# Arranque: como no hay paquete 'app', usamos main:app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

