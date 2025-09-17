# services/celery_tasks.py
"""
Stacks/bkn_notify/services/celery_tasks.py
Celery tasks para procesamiento de notificaciones
Workers que manejan envío de correos y Twilio en background - VERSION CORREGIDA
"""

import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from .celery_app import get_celery_app
from utils.config_loader import get_provider_config
from .smtp_sender import SMTPSender
from .api_sender import APISender
from services.database_service import DatabaseService

from constants import (
    REDIS_TASK_PREFIX, REDIS_LOG_PREFIX, MAX_RETRIES, RETRY_BACKOFF,
    CELERY_TASK_TIMEOUT
)

celery_app = get_celery_app()


class NotificationTask(Task):
    """
    Base task class con logging y manejo de errores
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logging.error(f"Task {task_id} failed: {exc}", exc_info=einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logging.warning(f"Task {task_id} retrying: {exc}")

    def on_success(self, retval, task_id, args, kwargs):
        logging.info(f"Task {task_id} completed successfully")


@celery_app.task(
    bind=True,
    base=NotificationTask,
    name="send_notification",
    max_retries=MAX_RETRIES,
    default_retry_delay=60,
    retry_backoff=RETRY_BACKOFF,
    time_limit=CELERY_TASK_TIMEOUT
)
def send_notification_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tarea principal para envío de notificaciones - SYNC wrapper
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_send_notification_async(self, payload))
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    base=NotificationTask,
    name="send_test_notification",
    max_retries=1,
    time_limit=120
)
def send_test_notification_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tarea para envío de notificaciones de prueba - SYNC wrapper
    """
    payload = dict(payload or {})
    payload.setdefault("provider", payload.get("provider") or "smtp_primary")
    payload.setdefault("message_id", payload.get("message_id") or f"test-{datetime.utcnow().timestamp()}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_send_notification_async(self, payload))
    finally:
        loop.close()


# -------------------------
# Funciones async internas
# -------------------------

async def _send_notification_async_old(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ CORREGIDO: Lógica async para envío de notificaciones (Email + Twilio)
    """
    message_id = payload.get("message_id")
    request_id = payload.get("request_id")
    provider = payload.get("provider")
    
    # ✅ NUEVO: Detectar tipo de notificación
    notification_type = payload.get("notification_type", "email")  # email por defecto
    
    log_extra = {
        "message_id": message_id,
        "request_id": request_id,
        "celery_task_id": self.request.id,
        "provider": provider,
        "notification_type": notification_type  # ✅ AGREGAR AL LOG
    }

    try:
        # Log de arranque y estado inicial
        await _log_task_start(message_id, payload, self.request.id)
        await _log_task_event(
            message_id=message_id,
            event="processing_started",
            message="Notification processing started",
            details={"celery_task_id": self.request.id, "provider": provider, "type": notification_type},
            celery_task_id=self.request.id,
        )
        await _update_task_status(
            message_id=message_id,
            status="processing",
            celery_task_id=self.request.id,
            additional_info={
                "started_at": datetime.utcnow().isoformat(),
                "provider": provider,
                "notification_type": notification_type
            },
        )

        # Actualizar estado en MySQL a processing
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="processing"
            )
            DatabaseService.add_notification_log(
                message_id=message_id,
                event_type="processing_started",
                event_status="info",
                event_message=f"{notification_type.title()} notification processing started",
                component="celery",
                provider=provider,
                details_json={"celery_task_id": self.request.id, "notification_type": notification_type}
            )
        except Exception as db_error:
            logging.error(f"Database update error for {message_id}: {db_error}")

        # Config del proveedor
        provider_config = get_provider_config(provider)
        if not provider_config:
            raise ValueError(f"Provider configuration not found: {provider}")

        # ✅ BIFURCAR: Procesamiento según tipo de notificación
        if notification_type == "twilio":
            # Procesar notificación Twilio (SMS/WhatsApp)
            send_result = await _send_twilio_async(payload, provider_config)
        else:
            # Procesar notificación de email (lógica original)
            rendered = await _prepare_email_content_async(payload)
            send_result = await _send_email_async(payload, rendered, provider_config)

        # Actualizar estado en MySQL a sent
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="sent",
                sent_at=datetime.utcnow()
            )
            DatabaseService.add_notification_log(
                message_id=message_id,
                event_type=f"{notification_type}_sent",
                event_status="success",
                event_message=f"{notification_type.title()} sent successfully",
                component="celery",
                provider=provider,
                details_json={
                    "provider_response": send_result.get("provider_response", {}),
                    "channel": send_result.get("channel")
                }
            )
        except Exception as db_error:
            logging.error(f"Database success update error for {message_id}: {db_error}")

        # Logs/estado de éxito
        await _log_task_event(
            message_id=message_id,
            event="sent_successfully",
            message=f"{notification_type.title()} sent successfully",
            details={
                "provider": provider,
                "provider_response": send_result.get("provider_response", {}),
                "sent_at": datetime.utcnow().isoformat(),
                "notification_type": notification_type
            },
            celery_task_id=self.request.id,
        )
        
        await _log_task_success(
            message_id=message_id,
            provider_response=send_result,
            celery_task_id=self.request.id,
        )
        
        await _update_task_status(
            message_id=message_id,
            status="success",
            celery_task_id=self.request.id,
            additional_info={
                "completed_at": datetime.utcnow().isoformat(),
                "provider_response": send_result,
                "final_status": "delivered",
                "notification_type": notification_type
            },
        )

        result = {
            "status": "success",
            "message_id": message_id,
            "provider": provider,
            "notification_type": notification_type,
            "sent_at": datetime.utcnow().isoformat(),
            "provider_response": send_result,
        }

        logging.info(f"{notification_type.title()} notification sent successfully", extra=log_extra)
        return result

    except Exception as exc:
        # Manejo de errores - igual que antes pero con notification_type
        should_retry = _should_retry_error(exc, self.request.retries)

        error_info = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "retry_count": self.request.retries,
            "max_retries": MAX_RETRIES,
            "notification_type": notification_type
        }

        if should_retry and self.request.retries < MAX_RETRIES:
            # Log de retry en MySQL
            try:
                DatabaseService.update_notification_status(
                    message_id=message_id,
                    status="failed",
                    retry_count=self.request.retries + 1
                )
                DatabaseService.add_notification_log(
                    message_id=message_id,
                    event_type="retry_scheduled",
                    event_status="warning",
                    event_message=f"Retry scheduled (attempt #{self.request.retries + 1})",
                    component="celery",
                    provider=provider,
                    details_json=error_info
                )
            except Exception as db_error:
                logging.error(f"Database retry update error for {message_id}: {db_error}")

            retry_delay = (RETRY_BACKOFF ** max(1, self.request.retries)) * 60
            next_retry_time = (datetime.utcnow() + timedelta(seconds=retry_delay)).isoformat()

            await _log_task_retry(
                message_id=message_id,
                retry_count=self.request.retries + 1,
                next_retry_time=next_retry_time,
                celery_task_id=self.request.id,
            )
            await _update_task_status(
                message_id=message_id,
                status="retry",
                celery_task_id=self.request.id,
                additional_info={
                    "error": error_info,
                    "retry_scheduled_at": datetime.utcnow().isoformat(),
                    "next_retry_eta": next_retry_time,
                    "notification_type": notification_type
                },
            )
            logging.warning(f"Retrying {notification_type} task in {retry_delay}s", extra=log_extra)
            raise self.retry(countdown=retry_delay, exc=exc)

        # Fallo definitivo en MySQL
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="failed"
            )
            DatabaseService.add_notification_log(
                message_id=message_id,
                event_type="failed_permanently",
                event_status="error",
                event_message=f"{notification_type.title()} notification failed permanently: {str(exc)}",
                component="celery",
                provider=provider,
                details_json=error_info
            )
        except Exception as db_error:
            logging.error(f"Database failure update error for {message_id}: {db_error}")

        await _log_task_failure(
            message_id=message_id,
            error=exc,
            celery_task_id=self.request.id,
            retry_count=self.request.retries,
            will_retry=False,
        )
        await _log_task_event(
            message_id=message_id,
            event="failed_permanently",
            message=f"{notification_type.title()} notification failed permanently: {exc}",
            details=error_info,
            celery_task_id=self.request.id,
        )
        await _update_task_status(
            message_id=message_id,
            status="failed",
            celery_task_id=self.request.id,
            additional_info={
                "failed_at": datetime.utcnow().isoformat(),
                "error": error_info,
                "final_status": "failed",
                "notification_type": notification_type
            },
        )
        logging.error(f"{notification_type.title()} notification failed permanently", extra=log_extra, exc_info=True)
        raise


async def _send_notification_async_old2(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ CORREGIDO: Lógica async para envío de notificaciones (Email + Twilio)
    CON INTEGRACIÓN DE PROVIDER_STATS
    """
    message_id = payload.get("message_id")
    request_id = payload.get("request_id")
    provider = payload.get("provider")
    
    # ✅ NUEVO: Detectar tipo de notificación
    notification_type = payload.get("notification_type", "email")  # email por defecto
    
    # ✅ NUEVO: Métricas de tiempo de procesamiento
    start_time = datetime.utcnow()
    
    log_extra = {
        "message_id": message_id,
        "request_id": request_id,
        "celery_task_id": self.request.id,
        "provider": provider,
        "notification_type": notification_type
    }

    try:
        # Log de arranque y estado inicial
        await _log_task_start(message_id, payload, self.request.id)
        await _log_task_event(
            message_id=message_id,
            event="processing_started",
            message="Notification processing started",
            details={"celery_task_id": self.request.id, "provider": provider, "type": notification_type},
            celery_task_id=self.request.id,
        )
        await _update_task_status(
            message_id=message_id,
            status="processing",
            celery_task_id=self.request.id,
            additional_info={
                "started_at": start_time.isoformat(),
                "provider": provider,
                "notification_type": notification_type
            },
        )

        # Actualizar estado en MySQL a processing
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="processing"
            )
            DatabaseService.add_notification_log(
                message_id=message_id,
                event_type="processing_started",
                event_status="info",
                event_message=f"{notification_type.title()} notification processing started",
                component="celery",
                provider=provider,
                details_json={"celery_task_id": self.request.id, "notification_type": notification_type}
            )
        except Exception as db_error:
            logging.error(f"Database update error for {message_id}: {db_error}")

        # Config del proveedor
        provider_config = get_provider_config(provider)
        if not provider_config:
            raise ValueError(f"Provider configuration not found: {provider}")

        # ✅ BIFURCAR: Procesamiento según tipo de notificación
        if notification_type == "twilio":
            # Procesar notificación Twilio (SMS/WhatsApp)
            send_result = await _send_twilio_async(payload, provider_config)
        else:
            # Procesar notificación de email (lógica original)
            rendered = await _prepare_email_content_async(payload)
            send_result = await _send_email_async(payload, rendered, provider_config)

        # ✅ NUEVO: Calcular tiempo de procesamiento
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Actualizar estado en MySQL a sent
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="sent",
                sent_at=end_time
            )
            DatabaseService.add_notification_log(
                message_id=message_id,
                event_type=f"{notification_type}_sent",
                event_status="success",
                event_message=f"{notification_type.title()} sent successfully",
                component="celery",
                provider=provider,
                processing_time_ms=processing_time_ms,  # ✅ NUEVO: Registrar tiempo
                details_json={
                    "provider_response": send_result.get("provider_response", {}),
                    "channel": send_result.get("channel"),
                    "processing_time_ms": processing_time_ms
                }
            )
            
            # ✅ NUEVO: Actualizar estadísticas de proveedor (ÉXITO)
            DatabaseService.update_provider_stats(
                provider=provider,
                stat_type="sent",
                processing_time_ms=processing_time_ms
            )
            
        except Exception as db_error:
            logging.error(f"Database success update error for {message_id}: {db_error}")

        # Logs/estado de éxito
        await _log_task_event(
            message_id=message_id,
            event="sent_successfully",
            message=f"{notification_type.title()} sent successfully",
            details={
                "provider": provider,
                "provider_response": send_result.get("provider_response", {}),
                "sent_at": end_time.isoformat(),
                "notification_type": notification_type,
                "processing_time_ms": processing_time_ms  # ✅ NUEVO
            },
            celery_task_id=self.request.id,
        )
        
        await _log_task_success(
            message_id=message_id,
            provider_response=send_result,
            celery_task_id=self.request.id,
            delivery_time=processing_time_ms / 1000.0  # ✅ NUEVO: convertir a segundos
        )
        
        await _update_task_status(
            message_id=message_id,
            status="success",
            celery_task_id=self.request.id,
            additional_info={
                "completed_at": end_time.isoformat(),
                "provider_response": send_result,
                "final_status": "delivered",
                "notification_type": notification_type,
                "processing_time_ms": processing_time_ms  # ✅ NUEVO
            },
        )

        result = {
            "status": "success",
            "message_id": message_id,
            "provider": provider,
            "notification_type": notification_type,
            "sent_at": end_time.isoformat(),
            "provider_response": send_result,
            "processing_time_ms": processing_time_ms  # ✅ NUEVO
        }

        logging.info(f"{notification_type.title()} notification sent successfully", extra=log_extra)
        return result

    except Exception as exc:
        # ✅ NUEVO: Calcular tiempo hasta el fallo
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Manejo de errores - igual que antes pero con notification_type
        should_retry = _should_retry_error(exc, self.request.retries)

        error_info = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "retry_count": self.request.retries,
            "max_retries": MAX_RETRIES,
            "notification_type": notification_type,
            "processing_time_ms": processing_time_ms  # ✅ NUEVO
        }

        if should_retry and self.request.retries < MAX_RETRIES:
            # Log de retry en MySQL
            try:
                DatabaseService.update_notification_status(
                    message_id=message_id,
                    status="failed",
                    retry_count=self.request.retries + 1
                )
                DatabaseService.add_notification_log(
                    message_id=message_id,
                    event_type="retry_scheduled",
                    event_status="warning",
                    event_message=f"Retry scheduled (attempt #{self.request.retries + 1})",
                    component="celery",
                    provider=provider,
                    processing_time_ms=processing_time_ms,  # ✅ NUEVO
                    details_json=error_info
                )
            except Exception as db_error:
                logging.error(f"Database retry update error for {message_id}: {db_error}")

            retry_delay = (RETRY_BACKOFF ** max(1, self.request.retries)) * 60
            next_retry_time = (datetime.utcnow() + timedelta(seconds=retry_delay)).isoformat()

            await _log_task_retry(
                message_id=message_id,
                retry_count=self.request.retries + 1,
                next_retry_time=next_retry_time,
                celery_task_id=self.request.id,
            )
            await _update_task_status(
                message_id=message_id,
                status="retry",
                celery_task_id=self.request.id,
                additional_info={
                    "error": error_info,
                    "retry_scheduled_at": datetime.utcnow().isoformat(),
                    "next_retry_eta": next_retry_time,
                    "notification_type": notification_type,
                    "processing_time_ms": processing_time_ms  # ✅ NUEVO
                },
            )
            logging.warning(f"Retrying {notification_type} task in {retry_delay}s", extra=log_extra)
            raise self.retry(countdown=retry_delay, exc=exc)

        # ✅ NUEVO: Fallo definitivo - actualizar estadísticas de proveedor (FALLO)
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="failed"
            )
            DatabaseService.add_notification_log(
                message_id=message_id,
                event_type="failed_permanently",
                event_status="error",
                event_message=f"{notification_type.title()} notification failed permanently: {str(exc)}",
                component="celery",
                provider=provider,
                processing_time_ms=processing_time_ms,  # ✅ NUEVO
                details_json=error_info
            )
            
            # ✅ NUEVO: Actualizar estadísticas de proveedor (FALLO)
            DatabaseService.update_provider_stats(
                provider=provider,
                stat_type="failed",
                processing_time_ms=processing_time_ms
            )
            
        except Exception as db_error:
            logging.error(f"Database failure update error for {message_id}: {db_error}")

        await _log_task_failure(
            message_id=message_id,
            error=exc,
            celery_task_id=self.request.id,
            retry_count=self.request.retries,
            will_retry=False,
        )
        await _log_task_event(
            message_id=message_id,
            event="failed_permanently",
            message=f"{notification_type.title()} notification failed permanently: {exc}",
            details=error_info,
            celery_task_id=self.request.id,
        )
        await _update_task_status(
            message_id=message_id,
            status="failed",
            celery_task_id=self.request.id,
            additional_info={
                "failed_at": end_time.isoformat(),
                "error": error_info,
                "final_status": "failed",
                "notification_type": notification_type,
                "processing_time_ms": processing_time_ms  # ✅ NUEVO
            },
        )
        logging.error(f"{notification_type.title()} notification failed permanently", extra=log_extra, exc_info=True)
        raise


# ✅ VERSIÓN CORREGIDA DE _send_notification_async con medición de tiempo
async def _send_notification_async(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Lógica async para envío de notificaciones (Email + Twilio)
    CON INTEGRACIÓN COMPLETA DE PROVIDER_STATS
    """
    message_id = payload.get("message_id")
    request_id = payload.get("request_id")
    provider = payload.get("provider")
    
    # Detectar tipo de notificación
    notification_type = payload.get("notification_type", "email")
    
    # ✅ Métricas de tiempo de procesamiento
    start_time = datetime.utcnow()
    
    log_extra = {
        "message_id": message_id,
        "request_id": request_id,
        "celery_task_id": self.request.id,
        "provider": provider,
        "notification_type": notification_type
    }

    try:
        # Log de arranque y estado inicial
        await _log_task_start(message_id, payload, self.request.id)
        await _log_task_event(
            message_id=message_id,
            event="processing_started",
            message="Notification processing started",
            details={"celery_task_id": self.request.id, "provider": provider, "type": notification_type},
            celery_task_id=self.request.id,
        )
        await _update_task_status(
            message_id=message_id,
            status="processing",
            celery_task_id=self.request.id,
            additional_info={
                "started_at": start_time.isoformat(),
                "provider": provider,
                "notification_type": notification_type
            },
        )

        # Actualizar estado en MySQL a processing
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="processing"
            )
            DatabaseService.add_notification_log(
                message_id=message_id,
                event_type="processing_started",
                event_status="info",
                event_message=f"{notification_type.title()} notification processing started",
                component="celery",
                provider=provider,
                details_json={"celery_task_id": self.request.id, "notification_type": notification_type}
            )
        except Exception as db_error:
            logging.error(f"Database update error for {message_id}: {db_error}")

        # Config del proveedor
        provider_config = get_provider_config(provider)
        if not provider_config:
            raise ValueError(f"Provider configuration not found: {provider}")

        # Procesamiento según tipo de notificación
        if notification_type == "twilio":
            # Procesar notificación Twilio (SMS/WhatsApp)
            send_result = await _send_twilio_async(payload, provider_config)
        else:
            # Procesar notificación de email (lógica original)
            rendered = await _prepare_email_content_async(payload)
            send_result = await _send_email_async(payload, rendered, provider_config)

        # ✅ Calcular tiempo de procesamiento
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)

        # Actualizar estado en MySQL a sent
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="sent",
                sent_at=end_time
            )
            DatabaseService.add_notification_log(
                message_id=message_id,
                event_type=f"{notification_type}_sent",
                event_status="success",
                event_message=f"{notification_type.title()} sent successfully",
                component="celery",
                provider=provider,
                processing_time_ms=processing_time_ms,
                details_json={
                    "provider_response": send_result.get("provider_response", {}),
                    "channel": send_result.get("channel"),
                    "processing_time_ms": processing_time_ms
                }
            )
            
            # ✅ Actualizar estadísticas de proveedor (ÉXITO)
            DatabaseService.update_provider_stats(
                provider=provider,
                stat_type="sent",
                processing_time_ms=processing_time_ms
            )
            
        except Exception as db_error:
            logging.error(f"Database success update error for {message_id}: {db_error}")

        # Logs/estado de éxito
        await _log_task_event(
            message_id=message_id,
            event="sent_successfully",
            message=f"{notification_type.title()} sent successfully",
            details={
                "provider": provider,
                "provider_response": send_result.get("provider_response", {}),
                "sent_at": end_time.isoformat(),
                "notification_type": notification_type,
                "processing_time_ms": processing_time_ms
            },
            celery_task_id=self.request.id,
        )
        
        await _log_task_success(
            message_id=message_id,
            provider_response=send_result,
            celery_task_id=self.request.id,
            delivery_time=processing_time_ms / 1000.0
        )
        
        await _update_task_status(
            message_id=message_id,
            status="success",
            celery_task_id=self.request.id,
            additional_info={
                "completed_at": end_time.isoformat(),
                "provider_response": send_result,
                "final_status": "delivered",
                "notification_type": notification_type,
                "processing_time_ms": processing_time_ms
            },
        )

        result = {
            "status": "success",
            "message_id": message_id,
            "provider": provider,
            "notification_type": notification_type,
            "sent_at": end_time.isoformat(),
            "provider_response": send_result,
            "processing_time_ms": processing_time_ms
        }

        logging.info(f"{notification_type.title()} notification sent successfully", extra=log_extra)
        return result

    except Exception as exc:
        # Calcular tiempo hasta el fallo
        end_time = datetime.utcnow()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Manejo de errores
        should_retry = _should_retry_error(exc, self.request.retries)

        error_info = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "retry_count": self.request.retries,
            "max_retries": MAX_RETRIES,
            "notification_type": notification_type,
            "processing_time_ms": processing_time_ms
        }

        if should_retry and self.request.retries < MAX_RETRIES:
            # Log de retry en MySQL
            try:
                DatabaseService.update_notification_status(
                    message_id=message_id,
                    status="failed",
                    retry_count=self.request.retries + 1
                )
                DatabaseService.add_notification_log(
                    message_id=message_id,
                    event_type="retry_scheduled",
                    event_status="warning",
                    event_message=f"Retry scheduled (attempt #{self.request.retries + 1})",
                    component="celery",
                    provider=provider,
                    processing_time_ms=processing_time_ms,
                    details_json=error_info
                )
            except Exception as db_error:
                logging.error(f"Database retry update error for {message_id}: {db_error}")

            retry_delay = (RETRY_BACKOFF ** max(1, self.request.retries)) * 60
            next_retry_time = (datetime.utcnow() + timedelta(seconds=retry_delay)).isoformat()

            await _log_task_retry(
                message_id=message_id,
                retry_count=self.request.retries + 1,
                next_retry_time=next_retry_time,
                celery_task_id=self.request.id,
            )
            await _update_task_status(
                message_id=message_id,
                status="retry",
                celery_task_id=self.request.id,
                additional_info={
                    "error": error_info,
                    "retry_scheduled_at": datetime.utcnow().isoformat(),
                    "next_retry_eta": next_retry_time,
                    "notification_type": notification_type,
                    "processing_time_ms": processing_time_ms
                },
            )
            logging.warning(f"Retrying {notification_type} task in {retry_delay}s", extra=log_extra)
            raise self.retry(countdown=retry_delay, exc=exc)

        # Fallo definitivo - actualizar estadísticas de proveedor (FALLO)
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="failed"
            )
            DatabaseService.add_notification_log(
                message_id=message_id,
                event_type="failed_permanently",
                event_status="error",
                event_message=f"{notification_type.title()} notification failed permanently: {str(exc)}",
                component="celery",
                provider=provider,
                processing_time_ms=processing_time_ms,
                details_json=error_info
            )
            
            # ✅ Actualizar estadísticas de proveedor (FALLO)
            DatabaseService.update_provider_stats(
                provider=provider,
                stat_type="failed",
                processing_time_ms=processing_time_ms
            )
            
        except Exception as db_error:
            logging.error(f"Database failure update error for {message_id}: {db_error}")

        await _log_task_failure(
            message_id=message_id,
            error=exc,
            celery_task_id=self.request.id,
            retry_count=self.request.retries,
            will_retry=False,
        )
        await _log_task_event(
            message_id=message_id,
            event="failed_permanently",
            message=f"{notification_type.title()} notification failed permanently: {exc}",
            details=error_info,
            celery_task_id=self.request.id,
        )
        await _update_task_status(
            message_id=message_id,
            status="failed",
            celery_task_id=self.request.id,
            additional_info={
                "failed_at": end_time.isoformat(),
                "error": error_info,
                "final_status": "failed",
                "notification_type": notification_type,
                "processing_time_ms": processing_time_ms
            },
        )
        logging.error(f"{notification_type.title()} notification failed permanently", extra=log_extra, exc_info=True)
        raise
    

def _should_retry_error(exc: Exception, current_retries: int) -> bool:
    """
    Heurística simple para decidir reintentos
    """
    transient_errors = (
        ConnectionError,
        TimeoutError,
    )
    msg = str(exc).lower()
    if isinstance(exc, transient_errors):
        return True
    if "timeout" in msg or "temporarily" in msg or "rate limit" in msg:
        return True
    return current_retries < MAX_RETRIES


async def _prepare_email_content_async(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Prepara/normaliza el contenido a enviar (SOLO PARA EMAIL)
    """
    
    #template_id = payload.get("template_id")
    template_id=False
    variables = payload.get("vars") or {}

    subject = payload.get("subject")
    body_text = payload.get("body_text")
    body_html = payload.get("body_html")

    if template_id:
        try:
            # Renderizar template
            from services.template_renderer import render_template
            rendered = await render_template(
                template_id=template_id,
                variables=variables
            )
            subject = rendered.get("subject", subject)
            body_text = rendered.get("body_text", body_text)
            body_html = rendered.get("body_html", body_html)
        except Exception as e:
            logging.error(f"Template rendering failed: {e}")
            # Continuar con contenido fallback si existe

    return {
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
    }


async def _send_twilio_sms(payload: Dict[str, Any], provider_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Envío SMS real via Twilio SDK
    """
    
    to_numbers = payload.get("to", [])
    body_text = payload.get("body_text", "")
    message_id = payload.get("message_id")
    start_time = datetime.utcnow()
    
    try:
        # ✅ CORREGIDO: Usar TwilioService con provider_config
        from services.twilio_service import TwilioService
        
        twilio_service = TwilioService(provider_config)
        
        # Enviar a cada número (Twilio requiere envíos individuales)
        results = []
        successful_sends = 0
        
        for to_number in to_numbers:
            try:
                result = await twilio_service.send_sms(
                    to=to_number,
                    message=body_text,
                    message_id=f"{message_id}-{to_number.replace('+', '')}",
                    custom_params=payload.get("custom_options", {})
                )
                results.append(result)
                if result.get("success"):
                    successful_sends += 1
                    
            except Exception as sms_error:
                logging.error(f"SMS to {to_number} failed: {sms_error}")
                results.append({
                    "success": False,
                    "to": to_number,
                    "error": str(sms_error)
                })
        
        # Calcular tiempo total
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return {
            "success": successful_sends > 0,
            "message_id": message_id,
            "provider": "twilio_sms",
            "provider_config": provider_config.get("name", "twilio_sms"),
            "recipients_count": len(to_numbers),
            "successful_sends": successful_sends,
            "failed_sends": len(to_numbers) - successful_sends,
            "processing_time_ms": processing_time_ms,
            "provider_response": {
                "sms_status": "sent" if successful_sends > 0 else "failed",
                "delivery_status": "processed",
                "results": results,
                "response": f"SMS sent to {successful_sends}/{len(to_numbers)} recipients"
            },
            "sent_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        logging.error(f"Twilio SMS service failed: {e}")
        
        return {
            "success": False,
            "message_id": message_id,
            "provider": "twilio_sms",
            "provider_config": provider_config.get("name", "twilio_sms"),
            "recipients_count": len(to_numbers),
            "successful_sends": 0,
            "failed_sends": len(to_numbers),
            "processing_time_ms": processing_time_ms,
            "error": str(e),
            "provider_response": {
                "sms_status": "failed",
                "delivery_status": "rejected",
                "response": f"SMS service failed: {str(e)}"
            },
            "sent_at": datetime.utcnow().isoformat()
        }


async def _send_twilio_whatsapp(payload: Dict[str, Any], provider_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Envío WhatsApp real vía Twilio SDK
    """
    
    to_numbers = payload.get("to", [])
    body_text = payload.get("body_text", "")
    message_id = payload.get("message_id")
    #template_id = payload.get("template_id")
    template_id=False
    template_vars = payload.get("vars", {})
    start_time = datetime.utcnow()
    
    try:
        # ✅ CORREGIDO: Usar TwilioService con provider_config
        from services.twilio_service import TwilioService
        
        twilio_service = TwilioService(provider_config)
        
        # Enviar a cada número
        results = []
        successful_sends = 0
        
        for to_number in to_numbers:
            try:
                if template_id:
                    # Convertir template_vars a lista para Twilio
                    template_params = list(template_vars.values()) if template_vars else []
                    result = await twilio_service.send_whatsapp(
                        to=to_number,
                        template_name=template_id,
                        template_params=template_params,
                        message_id=f"{message_id}-{to_number.replace('+', '')}",
                        custom_params=payload.get("custom_options", {})
                    )
                else:
                    result = await twilio_service.send_whatsapp(
                        to=to_number,
                        message=body_text,
                        message_id=f"{message_id}-{to_number.replace('+', '')}",
                        custom_params=payload.get("custom_options", {})
                    )
                
                results.append(result)
                if result.get("success"):
                    successful_sends += 1
                    
            except Exception as wa_error:
                logging.error(f"WhatsApp to {to_number} failed: {wa_error}")
                results.append({
                    "success": False,
                    "to": to_number,
                    "error": str(wa_error)
                })
        
        # Calcular tiempo total
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return {
            "success": successful_sends > 0,
            "message_id": message_id,
            "provider": "twilio_whatsapp",
            "provider_config": provider_config.get("name", "twilio_whatsapp"),
            "recipients_count": len(to_numbers),
            "successful_sends": successful_sends,
            "failed_sends": len(to_numbers) - successful_sends,
            "processing_time_ms": processing_time_ms,
            "provider_response": {
                "whatsapp_status": "sent" if successful_sends > 0 else "failed",
                "delivery_status": "processed",
                "results": results,
                "response": f"WhatsApp sent to {successful_sends}/{len(to_numbers)} recipients",
                "used_template": bool(template_id)
            },
            "sent_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        logging.error(f"Twilio WhatsApp service failed: {e}")
        
        return {
            "success": False,
            "message_id": message_id,
            "provider": "twilio_whatsapp",
            "provider_config": provider_config.get("name", "twilio_whatsapp"),
            "recipients_count": len(to_numbers),
            "successful_sends": 0,
            "failed_sends": len(to_numbers),
            "processing_time_ms": processing_time_ms,
            "error": str(e),
            "provider_response": {
                "whatsapp_status": "failed",
                "delivery_status": "rejected",
                "response": f"WhatsApp service failed: {str(e)}",
                "used_template": bool(template_id)
            },
            "sent_at": datetime.utcnow().isoformat()
        }


async def _send_twilio_async(payload: Dict[str, Any], provider_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Maneja envío de notificaciones Twilio (SMS/WhatsApp)
    """
    provider_type = provider_config.get("provider_type", "")
    
    try:
        if provider_type == "twilio_sms":
            result = await _send_twilio_sms(payload, provider_config)
            return {"channel": "twilio_sms", **result}
            
        elif provider_type == "twilio_whatsapp":
            result = await _send_twilio_whatsapp(payload, provider_config)
            return {"channel": "twilio_whatsapp", **result}
            
        else:
            raise ValueError(f"Unsupported Twilio provider type: {provider_type}")
            
    except Exception as e:
        logging.error(f"Twilio sending failed: {e}")
        raise



async def _send_email_async(
    payload: Dict[str, Any],
    rendered: Dict[str, Optional[str]],
    provider_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    ✅ MANTENIDO: Maneja envío de emails (SMTP o API) - LÓGICA ORIGINAL
    """
    to = payload.get("to") or []
    cc = payload.get("cc") or []
    bcc = payload.get("bcc") or []
    custom_headers = payload.get("headers") or {}
    attachments = payload.get("attachments") or []
    message_id = payload.get("message_id")

    subject = rendered.get("subject")
    body_text = rendered.get("body_text")
    body_html = rendered.get("body_html")

    channel = (provider_config.get("type") or "").lower()

    if channel == "smtp":
        sender = SMTPSender(provider_config)
        result = await sender.send_email(
            to=to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            message_id=message_id,
            custom_headers=custom_headers,
        )
        return {"channel": "smtp", **result}

    elif channel == "api":
        sender = APISender(provider_config)
        result = await sender.send_email(
            to=to,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            message_id=message_id,
            custom_headers=custom_headers,
        )
        return {"channel": "api", **result}

    raise ValueError(f"Unsupported email provider type: {channel}")


# -------------------------
# Logging helpers async - MANTENIDOS IGUAL
# -------------------------

async def _log_task_event(
    message_id: str,
    event: str,
    message: str,
    level: str = "INFO",
    details: Dict[str, Any] = None,
    celery_task_id: str = None
):
    """Log de evento de tarea en Redis"""
    try:
        from utils.redis_client import get_redis_client, RedisHelper
        from constants import REDIS_LOG_PREFIX

        redis_client = await get_redis_client()
        redis_helper = RedisHelper(redis_client)

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "message_id": message_id,
            "event": event,
            "level": level,
            "message": message,
            "details": details or {},
            "celery_task_id": celery_task_id
        }

        log_key = f"{REDIS_LOG_PREFIX}{message_id}"
        await redis_helper.push_log(log_key, log_entry, max_entries=500)

        log_level = getattr(logging, level.upper(), logging.INFO)
        logging.log(log_level, f"[{message_id}] {event}: {message}", extra={
            "message_id": message_id,
            "event": event,
            "celery_task_id": celery_task_id,
            **log_entry["details"]
        })

    except Exception as e:
        logging.error(f"Task logging failed for {message_id}: {e}")


async def _log_task_start(message_id: str, task_payload: Dict[str, Any], celery_task_id: str):
    """Log de inicio de tarea"""
    notification_type = task_payload.get("notification_type", "email")
    await _log_task_event(
        message_id=message_id,
        event="task_started",
        message=f"{notification_type.title()} delivery task started",
        level="INFO",
        details={
            "recipients_count": len(task_payload.get("to", [])),
            "has_template": bool(task_payload.get("template_id")),
            "provider": task_payload.get("provider"),
            "routing_hint": task_payload.get("routing_hint"),
            "notification_type": notification_type
        },
        celery_task_id=celery_task_id
    )


async def _log_task_success(
    message_id: str,
    provider_response: Dict[str, Any],
    celery_task_id: str,
    delivery_time: float = None
):
    """Log de tarea completada exitosamente"""
    await _log_task_event(
        message_id=message_id,
        event="notification_sent",
        message="Notification sent successfully",
        level="INFO",
        details={
            "provider_response": provider_response,
            "delivery_time_seconds": delivery_time,
            "success": True
        },
        celery_task_id=celery_task_id
    )


async def _log_task_failure(
    message_id: str,
    error: Exception,
    celery_task_id: str,
    retry_count: int = 0,
    will_retry: bool = False
):
    """Log de fallo de tarea"""
    await _log_task_event(
        message_id=message_id,
        event="task_failed" if not will_retry else "task_retry",
        message=f"Notification delivery failed: {str(error)}",
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


async def _log_task_retry(message_id: str, retry_count: int, next_retry_time: str, celery_task_id: str):
    """Log de reintento de tarea"""
    await _log_task_event(
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


async def _update_task_status(
    message_id: str,
    status: str,
    celery_task_id: str,
    additional_info: Dict[str, Any] = None
):
    """Actualiza estado de tarea en Redis"""
    try:
        from utils.redis_client import get_redis_client
        from constants import REDIS_TASK_PREFIX

        redis_client = await get_redis_client()

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

        task_data.update({
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
            **(additional_info or {})
        })

        await redis_client.setex(task_key, 86400, json.dumps(task_data))

        await _log_task_event(
            message_id=message_id,
            event="status_updated",
            message=f"Task status updated to {status}",
            level="DEBUG",
            details={"new_status": status, **task_data},
            celery_task_id=celery_task_id
        )

    except Exception as e:
        logging.error(f"Failed to update task status for {message_id}: {e}")

