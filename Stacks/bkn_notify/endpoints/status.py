"""
Status endpoints - Consulta estado y logs de notificaciones
"""

import json
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query

from constants import (
    HTTP_404_NOT_FOUND, TASK_STATES, REDIS_TASK_PREFIX, REDIS_LOG_PREFIX
)
from models.status_response import StatusResponse, LogEntry, LogsResponse
from utils.redis_client import get_redis_client
from services.celery_app import get_celery_app

router = APIRouter()


@router.get("/notify/{message_id}/status", response_model=StatusResponse)
async def get_notification_status(
    message_id: str,
    redis_client = Depends(get_redis_client)
):
    """
    Consulta el estado actual de una notificación
    
    Estados posibles:
    - pending: En cola, no procesada aún
    - processing: Siendo procesada por Celery worker
    - success: Enviada exitosamente 
    - failed: Falló el envío
    - retry: En proceso de reintento
    - cancelled: Cancelada manualmente
    """
    
    try:
        # Buscar información de la tarea en Redis
        task_key = f"{REDIS_TASK_PREFIX}{message_id}"
        task_data = await redis_client.get(task_key)
        
        if not task_data:
            logging.warning(f"Task not found in Redis: {message_id}")
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail={
                    "error": "notification_not_found",
                    "message": f"Notification with ID {message_id} not found"
                }
            )
        
        task_info = json.loads(task_data)
        celery_task_id = task_info.get("celery_task_id")
        
        # Consultar estado en Celery
        celery_app = get_celery_app()
        celery_result = celery_app.AsyncResult(celery_task_id)
        
        # Mapear estado de Celery a nuestros estados
        status = TASK_STATES.get(celery_result.state, "unknown")
        
        # Obtener información adicional según el estado
        result_info = {}
        error_info = None
        
        if celery_result.state == "SUCCESS":
            result_info = celery_result.result or {}
        elif celery_result.state == "FAILURE":
            error_info = {
                "error_type": type(celery_result.info).__name__ if celery_result.info else "UnknownError",
                "error_message": str(celery_result.info) if celery_result.info else "Unknown error occurred"
            }
        
        # Construir respuesta
        response = StatusResponse(
            message_id=message_id,
            status=status,
            celery_task_id=celery_task_id,
            created_at=task_info.get("created_at"),
            updated_at=datetime.utcnow().isoformat(),
            provider=task_info.get("provider"),
            recipients_count=len(task_info.get("to", [])),
            retry_count=getattr(celery_result, "retries", 0),
            result=result_info if result_info else None,
            error=error_info
        )
        
        logging.debug(f"Status retrieved for {message_id}: {status}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to get status for {message_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "status_retrieval_failed",
                "message": "Failed to retrieve notification status"
            }
        )


@router.get("/notify/{message_id}/logs", response_model=LogsResponse)
async def get_notification_logs(
    message_id: str,
    limit: int = Query(default=50, ge=1, le=1000, description="Number of log entries to return"),
    offset: int = Query(default=0, ge=0, description="Number of log entries to skip"),
    redis_client = Depends(get_redis_client)
):
    """
    Recupera los logs detallados de una notificación
    
    Incluye:
    - Eventos de procesamiento
    - Intentos de envío  
    - Errores y reintentos
    - Respuestas de proveedores
    """
    
    try:
        # Verificar que la notificación existe
        task_key = f"{REDIS_TASK_PREFIX}{message_id}"
        task_exists = await redis_client.exists(task_key)
        
        if not task_exists:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail={
                    "error": "notification_not_found", 
                    "message": f"Notification with ID {message_id} not found"
                }
            )
        
        # Obtener logs de Redis (almacenados como lista ordenada)
        log_key = f"{REDIS_LOG_PREFIX}{message_id}"
        
        # Contar total de logs
        total_logs = await redis_client.llen(log_key)
        
        if total_logs == 0:
            return LogsResponse(
                message_id=message_id,
                total_logs=0,
                logs=[],
                has_more=False
            )
        
        # Obtener logs con paginación (Redis LRANGE)
        # Nota: Redis indexa desde el inicio, ajustamos para paginación
        start_idx = offset
        end_idx = offset + limit - 1
        
        log_entries_raw = await redis_client.lrange(log_key, start_idx, end_idx)
        
        # Parsear y construir LogEntry objects
        log_entries = []
        for raw_entry in log_entries_raw:
            try:
                entry_data = json.loads(raw_entry)
                log_entry = LogEntry(
                    timestamp=entry_data.get("timestamp"),
                    level=entry_data.get("level", "INFO"),
                    event=entry_data.get("event"),
                    message=entry_data.get("message"),
                    details=entry_data.get("details", {})
                )
                log_entries.append(log_entry)
            except json.JSONDecodeError:
                # Skip malformed log entries
                continue
        
        # Determinar si hay más logs
        has_more = (offset + len(log_entries)) < total_logs
        
        response = LogsResponse(
            message_id=message_id,
            total_logs=total_logs,
            logs=log_entries,
            has_more=has_more,
            retrieved_at=datetime.utcnow().isoformat()
        )
        
        logging.debug(f"Retrieved {len(log_entries)} logs for {message_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to get logs for {message_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "logs_retrieval_failed",
                "message": "Failed to retrieve notification logs"
            }
        )


@router.delete("/notify/{message_id}")
async def cancel_notification(
    message_id: str,
    redis_client = Depends(get_redis_client)
):
    """
    Cancela una notificación pendiente
    Solo funciona si la tarea aún no ha sido procesada
    """
    
    try:
        # Buscar información de la tarea
        task_key = f"{REDIS_TASK_PREFIX}{message_id}"
        task_data = await redis_client.get(task_key)
        
        if not task_data:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail={
                    "error": "notification_not_found",
                    "message": f"Notification with ID {message_id} not found"
                }
            )
        
        task_info = json.loads(task_data)
        celery_task_id = task_info.get("celery_task_id")
        
        # Intentar revocar la tarea en Celery
        celery_app = get_celery_app()
        celery_app.control.revoke(celery_task_id, terminate=True)
        
        # Actualizar estado en Redis
        task_info["status"] = "cancelled"
        task_info["cancelled_at"] = datetime.utcnow().isoformat()
        await redis_client.setex(task_key, 3600, json.dumps(task_info))
        
        # Agregar log de cancelación
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO", 
            "event": "notification_cancelled",
            "message": "Notification cancelled by user request",
            "details": {"celery_task_id": celery_task_id}
        }
        
        log_key = f"{REDIS_LOG_PREFIX}{message_id}"
        await redis_client.lpush(log_key, json.dumps(log_entry))
        
        logging.info(f"Notification cancelled: {message_id}")
        
        return {
            "message_id": message_id,
            "status": "cancelled",
            "cancelled_at": task_info["cancelled_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to cancel notification {message_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "cancellation_failed",
                "message": "Failed to cancel notification"
            }
        )