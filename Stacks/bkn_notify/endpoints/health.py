"""
Health check endpoints
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.constants import SERVICE_NAME, API_VERSION, HTTP_503_SERVICE_UNAVAILABLE
from app.utils.redis_client import get_redis_client
from app.utils.config_loader import load_config

router = APIRouter()


@router.get("/healthz")
async def health_check():
    """
    Health check básico - indica si el servicio está vivo
    No requiere dependencias externas
    """
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": API_VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/readyz")
async def readiness_check():
    """
    Readiness check - verifica que el servicio esté listo para recibir tráfico
    Valida conexiones a dependencias críticas
    """
    checks = {
        "redis": "unknown",
        "config": "unknown",
        "celery": "unknown"
    }
    
    overall_status = "ready"
    
    # Verificar Redis
    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        checks["redis"] = "healthy"
        logging.debug("Redis connection verified")
    except Exception as e:
        checks["redis"] = f"failed: {str(e)}"
        overall_status = "not_ready"
        logging.error(f"Redis health check failed: {e}")
    
    # Verificar carga de configuración
    try:
        config = load_config()
        if config:
            checks["config"] = "healthy"
        else:
            checks["config"] = "failed: empty config"
            overall_status = "not_ready"
    except Exception as e:
        checks["config"] = f"failed: {str(e)}"
        overall_status = "not_ready"
        logging.error(f"Config health check failed: {e}")
    
    # Verificar Celery (básico - solo que Redis funcione como broker)
    try:
        # Si Redis funciona, Celery debería poder conectarse
        if checks["redis"] == "healthy":
            checks["celery"] = "healthy"
        else:
            checks["celery"] = "failed: redis unavailable"
            overall_status = "not_ready"
    except Exception as e:
        checks["celery"] = f"failed: {str(e)}"
        overall_status = "not_ready"
    
    response_data = {
        "status": overall_status,
        "service": SERVICE_NAME,
        "version": API_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }
    
    if overall_status == "not_ready":
        return JSONResponse(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            content=response_data
        )
    
    return response_data


@router.get("/metrics")
async def basic_metrics():
    """
    Métricas básicas del servicio
    Simple y sin sobre-ingeniería
    """
    try:
        redis_client = get_redis_client()
        
        # Estadísticas básicas de Redis
        redis_info = await redis_client.info()
        
        return {
            "service": SERVICE_NAME,
            "version": API_VERSION,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "redis_connected_clients": redis_info.get("connected_clients", 0),
                "redis_used_memory": redis_info.get("used_memory", 0),
                "redis_keyspace_hits": redis_info.get("keyspace_hits", 0),
                "redis_keyspace_misses": redis_info.get("keyspace_misses", 0)
            }
        }
    except Exception as e:
        logging.error(f"Metrics collection failed: {e}")
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Metrics unavailable"
        )