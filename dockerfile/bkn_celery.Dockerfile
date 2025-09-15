# Dockerfile para bkn_celery (Celery Workers)
# dockerfile/bkn_celery.Dockerfile
FROM python:3.11-slim

LABEL maintainer="notify-stack"
LABEL service="bkn_celery"
LABEL version="1.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    C_FORCE_ROOT=1

# Usuario no-root
RUN groupadd -r celery && useradd -r -g celery celery

# (Opcional) toolchain si alguna lib lo requiere
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Deps Python
COPY Stacks/bkn_notify/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código y configs
COPY Stacks/bkn_notify/ .
COPY Config/ ./Config/

# Crear directorios necesarios incluyendo beat-schedule
RUN mkdir -p logs templates beat-schedule && chown -R celery:celery /app

USER celery

# Healthcheck del worker (usa el mismo -A con el objeto celery_app)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD celery -A services.celery_app.celery_app inspect ping || exit 1

# Arranque del worker
CMD ["celery", "-A", "services.celery_app.celery_app", "worker", "--loglevel=info", "--concurrency=2"]