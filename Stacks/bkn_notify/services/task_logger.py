"""
Task logger service
Maneja logging específico de tareas Celery con Redis storage
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from constants import REDIS_LOG_PREFIX, REDIS_TASK_PREFIX
from utils.redis_client import get_redis_client, RedisHelper


async def log_task_event(
    message_id: str,
    event: str,
    message: str,
    level: str = "INFO",
    details: Dict[str, Any] = None,
    celery_task_id: str = None
):
    """
    Registra evento de tarea en logs Redis
    
    Args:
        message_id: ID único del mensaje/notificación
        event: Tipo de evento (task_started, email_sent, task_failed, etc.)
        message: Descripción del evento
        level: Nivel de log (DEBUG, INFO, WARNING, ERROR)
        details: Información adicional del evento
        celery_task_id: ID de la tarea Celery (opcional)
    """
    
    try:
        redis_client = await get_redis_client()
        redis_helper = RedisHelper(redis_client)
        
        # Preparar entrada de log
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "message_id": message_id,
            "event": event,
            "level": level,
            "message": message,
            "details": details or {},
            "celery_task_id": celery_task_id
        }
        
        # Agregar información adicional si está disponible
        if celery_task_id:
            log_entry["details"]["celery_task_id"] = celery_task_id
        
        # Guardar en Redis con clave específica del mensaje
        log_key = f"{REDIS_LOG_PREFIX}{message_id}"
        success = await redis_helper.push_log(log_key, log_entry, max_entries=500)
        
        if success:
            # También log en sistema de logging estándar
            log_level = getattr(logging, level.upper(), logging.INFO)
            logging.log(log_level, f"[{message_id}] {event}: {message}", extra={
                "message_id": message_id,
                "event": event,
                "celery_task_id": celery_task_id,
                **log_entry["details"]
            })
        else:
            logging.error(f"Failed to store log entry for message {message_id}")
            
    except Exception as e:
        logging.error(f"Task logging failed for {message_id}: {e}")


async def log_task_start(message_id: str, task_payload: Dict[str, Any], celery_task_id: str):
    """
    Log de inicio de tarea
    """
    await log_task_event(
        message_id=message_id,
        event="task_started",
        message="Email delivery task started",
        level="INFO",
        details={
            "recipients_count": len(task_payload.get("to", [])),
            "has_template": bool(task_payload.get("template_id")),
            "provider": task_payload.get("provider"),
            "routing_hint": task_payload.get("routing_hint")
        },
        celery_task_id=celery_task_id
    )


async def log_task_success(
    message_id: str, 
    provider_response: Dict[str, Any], 
    celery_task_id: str,
    delivery_time: float = None
):
    """
    Log de tarea completada exitosamente
    """
    await log_task_event(
        message_id=message_id,
        event="email_sent",
        message="Email sent successfully",
        level="INFO",
        details={
            "provider_response": provider_response,
            "delivery_time_seconds": delivery_time,
            "success": True
        },
        celery_task_id=celery_task_id
    )


async def log_task_failure(
    message_id: str,
    error: Exception,
    celery_task_id: str,
    retry_count: int = 0,
    will_retry: bool = False
):
    """
    Log de fallo de tarea
    """
    await log_task_event(
        message_id=message_id,
        event="task_failed" if not will_retry else "task_retry",
        message=f"Email delivery failed: {str(error)}",
        level="ERROR" if not will_retry else "WARNING",
        details={
            "error_type": type(error).__name__,
            "error_message": str(error),
            "retry_count": retry_count,
            "will_retry": will_retry,
            "success": False
        },
        celery_task_id=celery_task_id
    )


async def log_task_retry(message_id: str, retry_count: int, next_retry_time: str, celery_task_id: str):
    """
    Log de reintento de tarea
    """
    await log_task_event(
        message_id=message_id,
        event="task_retry_scheduled",
        message=f"Task retry scheduled (attempt #{retry_count})",
        level="WARNING",
        details={
            "retry_count": retry_count,
            "next_retry_time": next_retry_time
        },
        celery_task_id=celery_task_id
    )


async def log_provider_interaction(
    message_id: str,
    provider: str,
    action: str,
    response: Dict[str, Any],
    duration: float = None,
    celery_task_id: str = None
):
    """
    Log de interacción con proveedor externo
    """
    await log_task_event(
        message_id=message_id,
        event=f"provider_{action}",
        message=f"Provider {provider} {action}",
        level="DEBUG",
        details={
            "provider": provider,
            "action": action,
            "response": response,
            "duration_seconds": duration
        },
        celery_task_id=celery_task_id
    )


async def log_template_rendering(
    message_id: str,
    template_id: str,
    variables_count: int,
    success: bool,
    error: str = None,
    celery_task_id: str = None
):
    """
    Log de renderizado de template
    """
    await log_task_event(
        message_id=message_id,
        event="template_rendered" if success else "template_render_failed",
        message=f"Template {template_id} {'rendered' if success else 'failed'}",
        level="DEBUG" if success else "ERROR",
        details={
            "template_id": template_id,
            "variables_count": variables_count,
            "success": success,
            "error": error
        },
        celery_task_id=celery_task_id
    )


async def log_validation_result(
    message_id: str,
    validation_type: str,
    success: bool,
    details: Dict[str, Any] = None,
    celery_task_id: str = None
):
    """
    Log de resultados de validación
    """
    await log_task_event(
        message_id=message_id,
        event=f"validation_{validation_type}",
        message=f"Validation {validation_type} {'passed' if success else 'failed'}",
        level="DEBUG" if success else "WARNING",
        details={
            "validation_type": validation_type,
            "success": success,
            **(details or {})
        },
        celery_task_id=celery_task_id
    )


async def log_task_error(uuid: str, args: tuple, kwargs: dict):
    """
    Log de error global de Celery task
    Usado por el error handler de Celery
    """
    try:
        # Extraer message_id de los argumentos si es posible
        message_id = None
        if args and isinstance(args[0], dict):
            message_id = args[0].get("message_id")
        
        if not message_id:
            message_id = f"unknown-{uuid}"
        
        await log_task_event(
            message_id=message_id,
            event="celery_error",
            message="Celery task error handler triggered",
            level="ERROR",
            details={
                "celery_uuid": uuid,
                "args": str(args)[:500],  # Truncar si es muy largo
                "kwargs": str(kwargs)[:500]
            }
        )
        
    except Exception as e:
        logging.error(f"Failed to log Celery task error: {e}")


async def update_task_status(
    message_id: str,
    status: str,
    celery_task_id: str,
    additional_info: Dict[str, Any] = None
):
    """
    Actualiza estado de tarea en Redis
    """
    try:
        redis_client = await get_redis_client()
        
        # Obtener información existente de la tarea
        task_key = f"{REDIS_TASK_PREFIX}{message_id}"
        existing_data = await redis_client.get(task_key)
        
        if existing_data:
            task_data = json.loads(existing_data)
        else:
            task_data = {
                "message_id": message_id,
                "celery_task_id": celery_task_id,
                "created_at": datetime.utcnow().isoformat()
            }
        
        # Actualizar estado y timestamp
        task_data.update({
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
            **(additional_info or {})
        })
        
        # Guardar en Redis con TTL de 24 horas
        await redis_client.setex(task_key, 86400, json.dumps(task_data))
        
        # Log del cambio de estado
        await log_task_event(
            message_id=message_id,
            event="status_updated",
            message=f"Task status updated to {status}",
            level="DEBUG",
            details={"new_status": status, **task_data},
            celery_task_id=celery_task_id
        )
        
    except Exception as e:
        logging.error(f"Failed to update task status for {message_id}: {e}")


async def get_task_logs(message_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Recupera logs de una tarea específica
    """
    try:
        redis_client = await get_redis_client()
        log_key = f"{REDIS_LOG_PREFIX}{message_id}"
        
        # Obtener logs con paginación
        log_entries_raw = await redis_client.lrange(log_key, offset, offset + limit - 1)
        
        logs = []
        for raw_entry in log_entries_raw:
            try:
                log_entry = json.loads(raw_entry)
                logs.append(log_entry)
            except json.JSONDecodeError:
                continue
        
        return logs
        
    except Exception as e:
        logging.error(f"Failed to get task logs for {message_id}: {e}")
        return []


async def cleanup_old_task_logs(days_to_keep: int = 7) -> Dict[str, int]:
    """
    Limpia logs antiguos de Redis
    """
    try:
        redis_client = await get_redis_client()
        
        # Buscar todas las claves de logs
        log_keys = await redis_client.keys(f"{REDIS_LOG_PREFIX}*")
        
        cleaned_count = 0
        total_keys = len(log_keys)
        
        cutoff_timestamp = datetime.utcnow().timestamp() - (days_to_keep * 24 * 3600)
        
        for log_key in log_keys:
            try:
                # Obtener el log más reciente para verificar fecha
                latest_log = await redis_client.lindex(log_key, 0)
                if latest_log:
                    log_data = json.loads(latest_log)
                    log_timestamp = datetime.fromisoformat(log_data["timestamp"]).timestamp()
                    
                    if log_timestamp < cutoff_timestamp:
                        await redis_client.delete(log_key)
                        cleaned_count += 1
                        
            except (json.JSONDecodeError, KeyError, ValueError):
                # Si no se puede parsear, eliminar por seguridad
                await redis_client.delete(log_key)
                cleaned_count += 1
        
        logging.info(f"Cleaned up {cleaned_count} old log keys out of {total_keys}")
        
        return {
            "total_keys": total_keys,
            "cleaned_count": cleaned_count,
            "remaining_count": total_keys - cleaned_count,
            "days_kept": days_to_keep
        }
        
    except Exception as e:
        logging.error(f"Failed to cleanup old task logs: {e}")
        return {"error": str(e)}


def get_logging_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas básicas del sistema de logging
    """
    try:
        return {
            "log_prefix": REDIS_LOG_PREFIX,
            "task_prefix": REDIS_TASK_PREFIX,
            "max_entries_per_task": 500,
            "log_retention_days": 7,
            "features": [
                "task_lifecycle_tracking",
                "provider_interaction_logging", 
                "template_rendering_logs",
                "validation_result_logs",
                "automatic_cleanup"
            ]
        }
    except Exception as e:
        return {"error": str(e)}