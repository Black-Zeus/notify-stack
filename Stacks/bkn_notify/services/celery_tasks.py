# services/celery_tasks.py
"""
Celery tasks para procesamiento de notificaciones
Workers que manejan envío de correos en background
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from .celery_app import get_celery_app
from app.utils.config_loader import get_provider_config
from .smtp_sender import SMTPSender
from .api_sender import APISender

# Helpers de logging/estado en Redis y render de templates
from .task_logger import (
    log_task_event,
    log_task_start,
    log_task_success,
    log_task_failure,
    log_task_retry,
    update_task_status,
)
from .template_renderer import (
    render_template,                 # loader de templates (expuesto por tu util)
    validate_template_variables,     # opcional, para logs de validación
)

from app.constants import (
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
    default_retry_delay=60,          # 1 minuto
    retry_backoff=RETRY_BACKOFF,
    time_limit=CELERY_TASK_TIMEOUT
)
async def send_notification_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tarea principal para envío de notificaciones

    Args:
        payload: Dict con todos los datos del email

    Returns:
        Dict con resultado del envío
    """
    message_id = payload.get("message_id")
    request_id = payload.get("request_id")
    provider = payload.get("provider")

    log_extra = {
        "message_id": message_id,
        "request_id": request_id,
        "celery_task_id": self.request.id,
        "provider": provider,
    }

    try:
        # Log de arranque y estado inicial
        await log_task_start(message_id, payload, self.request.id)
        await log_task_event(
            message_id=message_id,
            event="processing_started",
            message="Notification processing started",
            details={"celery_task_id": self.request.id, "provider": provider},
            celery_task_id=self.request.id,
        )
        await update_task_status(
            message_id=message_id,
            status="processing",
            celery_task_id=self.request.id,
            additional_info={
                "started_at": datetime.utcnow().isoformat(),
                "provider": provider,
            },
        )

        # Render del contenido (si viene template_id/vars)
        rendered = await _prepare_email_content(payload)

        # Config del proveedor
        provider_config = get_provider_config(provider)
        if not provider_config:
            raise ValueError(f"Provider configuration not found: {provider}")

        # Envío con el proveedor
        send_result = await _send_email(payload, rendered, provider_config)

        # Logs/estado de éxito
        await log_task_event(
            message_id=message_id,
            event="sent_successfully",
            message="Email sent successfully",
            details={
                "provider": provider,
                "provider_response": send_result.get("provider_response", {}),
                "sent_at": datetime.utcnow().isoformat(),
            },
            celery_task_id=self.request.id,
        )
        await log_task_success(
            message_id=message_id,
            provider_response=send_result,
            celery_task_id=self.request.id,
        )
        await update_task_status(
            message_id=message_id,
            status="success",
            celery_task_id=self.request.id,
            additional_info={
                "completed_at": datetime.utcnow().isoformat(),
                "provider_response": send_result,
                "final_status": "delivered",
            },
        )

        result = {
            "status": "success",
            "message_id": message_id,
            "provider": provider,
            "sent_at": datetime.utcnow().isoformat(),
            "provider_response": send_result,
        }

        logging.info("Notification sent successfully", extra=log_extra)
        return result

    except Exception as exc:
        # ¿reintentamos?
        should_retry = _should_retry_error(exc, self.request.retries)

        error_info = {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "retry_count": self.request.retries,
            "max_retries": MAX_RETRIES,
        }

        if should_retry and self.request.retries < MAX_RETRIES:
            # Siguiente backoff (minutos -> segundos)
            retry_delay = (RETRY_BACKOFF ** max(1, self.request.retries)) * 60
            next_retry_time = (datetime.utcnow() + timedelta(seconds=retry_delay)).isoformat()

            await log_task_retry(
                message_id=message_id,
                retry_count=self.request.retries + 1,
                next_retry_time=next_retry_time,
                celery_task_id=self.request.id,
            )
            await update_task_status(
                message_id=message_id,
                status="retry",
                celery_task_id=self.request.id,
                additional_info={
                    "error": error_info,
                    "retry_scheduled_at": datetime.utcnow().isoformat(),
                    "next_retry_eta": next_retry_time,
                },
            )
            logging.warning(f"Retrying task in {retry_delay}s", extra=log_extra)
            raise self.retry(countdown=retry_delay, exc=exc)

        # Fallo definitivo
        await log_task_failure(
            message_id=message_id,
            error=exc,
            celery_task_id=self.request.id,
            retry_count=self.request.retries,
            will_retry=False,
        )
        await log_task_event(
            message_id=message_id,
            event="failed_permanently",
            message=f"Notification failed permanently: {exc}",
            details=error_info,
            celery_task_id=self.request.id,
        )
        await update_task_status(
            message_id=message_id,
            status="failed",
            celery_task_id=self.request.id,
            additional_info={
                "failed_at": datetime.utcnow().isoformat(),
                "error": error_info,
                "final_status": "failed",
            },
        )
        logging.error("Notification failed permanently", extra=log_extra, exc_info=True)
        raise


@celery_app.task(
    bind=True,
    base=NotificationTask,
    name="send_test_notification",
    max_retries=1,     # Menos reintentos para tests
    time_limit=120     # Timeout más corto
)
async def send_test_notification_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tarea para envío de notificaciones de prueba
    Similar a send_notification_task pero con logging especial
    """
    # Aquí podrías llamar al mismo pipeline y marcar `is_test=True` en logs
    payload = dict(payload or {})
    payload.setdefault("provider", payload.get("provider") or "smtp")
    payload.setdefault("message_id", payload.get("message_id") or f"test-{datetime.utcnow().timestamp()}")
    return await send_notification_task(payload)  # reutilizamos


# -------------------------
# Helpers internos
# -------------------------

def _should_retry_error(exc: Exception, current_retries: int) -> bool:
    """
    Heurística simple para decidir reintentos
    """
    transient_errors = (
        ConnectionError,
        TimeoutError,
    )
    # Errores de provider típicamente transitorios si contienen ciertos códigos
    msg = str(exc).lower()
    if isinstance(exc, transient_errors):
        return True
    if "timeout" in msg or "temporarily" in msg or "rate limit" in msg:
        return True
    # No reintentar si ya llegamos al máximo
    return current_retries < MAX_RETRIES


async def _prepare_email_content(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Prepara/normaliza el contenido a enviar:
    - Renderiza template si hay template_id/variables
    - Asegura que existan claves subject/body_text/body_html (aunque sea None)
    """
    template_id = payload.get("template_id")
    variables = payload.get("variables") or {}

    subject = payload.get("subject")
    body_text = payload.get("body_text")
    body_html = payload.get("body_html")

    if template_id:
        # Validación opcional (solo log)
        try:
            validate_template_variables(template_id, variables)
        except Exception:
            pass

        rendered = await render_template(
            template_id=template_id,
            variables=variables
        )
        # El renderer debe regresar campos consistentes (subject/body_text/body_html)
        subject = rendered.get("subject", subject)
        body_text = rendered.get("body_text", body_text)
        body_html = rendered.get("body_html", body_html)

    return {
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
    }


async def _send_email(
    payload: Dict[str, Any],
    rendered: Dict[str, Optional[str]],
    provider_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Decide el canal (SMTP o API) y efectúa el envío
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

    raise ValueError(f"Unsupported provider type: {channel}")
