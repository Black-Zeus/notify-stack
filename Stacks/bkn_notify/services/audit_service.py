"""
Audit Service - Logging de eventos a base de datos
Registra todas las acciones del sistema de notificaciones
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import time
import json

from services.database_service import DatabaseService
from models.database_models import NotificationStatus

logger = logging.getLogger(__name__)


class AuditService:
    """Servicio centralizado para auditoría y logging"""

    @staticmethod
    def log_notification_received(
        message_id: str,
        request_data: Dict[str, Any],
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        api_key_hash: Optional[str] = None
    ) -> bool:
        """Registra recepción de notificación en API"""
        
        details = {
            "to_email": request_data.get("to"),
            "template_id": request_data.get("template_id"),
            "has_attachments": bool(request_data.get("attachments")),
            "source_ip": source_ip,
            "user_agent": user_agent,
            "payload_size": len(json.dumps(request_data))
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="notification_received",
            event_status="accepted",
            event_message="Notification received via API",
            details_json=details,
            component="api"
        ) is not None

    @staticmethod
    def log_validation_error(
        message_id: str,
        errors: List[str],
        request_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Registra errores de validación"""
        
        details = {
            "validation_errors": errors,
            "request_keys": list(request_data.keys()) if request_data else []
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="validation_error",
            event_status="rejected",
            event_message=f"Validation failed: {', '.join(errors)}",
            details_json=details,
            component="api"
        ) is not None

    @staticmethod
    def log_task_queued(
        message_id: str,
        celery_task_id: str,
        provider: str,
        queue_name: Optional[str] = None
    ) -> bool:
        """Registra tarea encolada en Celery"""
        
        details = {
            "celery_task_id": celery_task_id,
            "provider": provider,
            "queue_name": queue_name,
            "queued_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="task_queued",
            event_status="PENDING",
            event_message=f"Task queued for provider {provider}",
            details_json=details,
            component="api",
            provider=provider
        ) is not None

    @staticmethod
    def log_task_started(
        message_id: str,
        worker_name: Optional[str] = None,
        provider: Optional[str] = None
    ) -> bool:
        """Registra inicio de procesamiento en worker"""
        
        details = {
            "worker_name": worker_name,
            "started_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="task_started",
            event_status="processing",
            event_message="Email delivery task started",
            details_json=details,
            component="celery",
            provider=provider
        ) is not None

    @staticmethod
    def log_template_rendered(
        message_id: str,
        template_id: str,
        rendered_subject: str,
        has_html: bool,
        has_text: bool,
        variables: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Registra renderizado de template"""
        
        details = {
            "template_id": template_id,
            "subject_length": len(rendered_subject),
            "has_html_body": has_html,
            "has_text_body": has_text,
            "variables_count": len(variables) if variables else 0,
            "rendered_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="template_rendered",
            event_status="success",
            event_message=f"Template {template_id} rendered successfully",
            details_json=details,
            component="celery"
        ) is not None

    @staticmethod
    def log_template_error(
        message_id: str,
        template_id: str,
        error_message: str,
        error_type: Optional[str] = None
    ) -> bool:
        """Registra error en renderizado de template"""
        
        details = {
            "template_id": template_id,
            "error_type": error_type,
            "error_message": error_message
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="template_error",
            event_status="failed",
            event_message=f"Template rendering failed: {error_message}",
            details_json=details,
            component="celery"
        ) is not None

    @staticmethod
    def log_email_sending(
        message_id: str,
        provider: str,
        smtp_host: Optional[str] = None,
        recipients_count: int = 1
    ) -> bool:
        """Registra inicio de envío de email"""
        
        details = {
            "provider": provider,
            "smtp_host": smtp_host,
            "recipients_count": recipients_count,
            "sending_started_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="email_sending",
            event_status="processing",
            event_message=f"Sending email via {provider}",
            details_json=details,
            component="smtp",
            provider=provider
        ) is not None

    @staticmethod
    def log_email_sent(
        message_id: str,
        provider: str,
        provider_response: Optional[Dict[str, Any]] = None,
        delivery_time_ms: Optional[int] = None
    ) -> bool:
        """Registra email enviado exitosamente"""
        
        details = {
            "provider": provider,
            "provider_response": provider_response,
            "delivery_time_ms": delivery_time_ms,
            "sent_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="email_sent",
            event_status="success",
            event_message="Email sent successfully",
            details_json=details,
            component="smtp",
            provider=provider,
            processing_time_ms=delivery_time_ms
        ) is not None

    @staticmethod
    def log_email_failed(
        message_id: str,
        provider: str,
        error_message: str,
        error_code: Optional[str] = None,
        retry_attempt: int = 0
    ) -> bool:
        """Registra fallo en envío de email"""
        
        details = {
            "provider": provider,
            "error_message": error_message,
            "error_code": error_code,
            "retry_attempt": retry_attempt,
            "failed_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="email_failed",
            event_status="failed",
            event_message=f"Email delivery failed: {error_message}",
            details_json=details,
            component="smtp",
            provider=provider
        ) is not None

    @staticmethod
    def log_retry_scheduled(
        message_id: str,
        retry_attempt: int,
        retry_delay_seconds: int,
        max_retries: int
    ) -> bool:
        """Registra reintento programado"""
        
        details = {
            "retry_attempt": retry_attempt,
            "retry_delay_seconds": retry_delay_seconds,
            "max_retries": max_retries,
            "next_retry_at": (datetime.utcnow().timestamp() + retry_delay_seconds)
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="retry_scheduled",
            event_status="PENDING",
            event_message=f"Retry {retry_attempt}/{max_retries} scheduled in {retry_delay_seconds}s",
            details_json=details,
            component="celery"
        ) is not None

    @staticmethod
    def log_max_retries_exceeded(
        message_id: str,
        total_attempts: int,
        last_error: str
    ) -> bool:
        """Registra agotamiento de reintentos"""
        
        details = {
            "total_attempts": total_attempts,
            "last_error": last_error,
            "abandoned_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="max_retries_exceeded",
            event_status="abandoned",
            event_message=f"Abandoned after {total_attempts} attempts",
            details_json=details,
            component="celery"
        ) is not None

    @staticmethod
    def log_idempotency_hit(
        message_id: str,
        idempotency_key: str,
        original_message_id: str
    ) -> bool:
        """Registra hit de idempotencia"""
        
        details = {
            "idempotency_key": idempotency_key,
            "original_message_id": original_message_id,
            "duplicate_detected_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="idempotency_hit",
            event_status="duplicate",
            event_message=f"Duplicate request detected, returning original: {original_message_id}",
            details_json=details,
            component="api"
        ) is not None

    @staticmethod
    def log_rate_limit_hit(
        message_id: str,
        rate_limit_key: str,
        requests_count: int,
        window_seconds: int
    ) -> bool:
        """Registra hit de rate limiting"""
        
        details = {
            "rate_limit_key": rate_limit_key,
            "requests_count": requests_count,
            "window_seconds": window_seconds,
            "blocked_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="rate_limit_hit",
            event_status="blocked",
            event_message=f"Rate limit exceeded: {requests_count} requests in {window_seconds}s",
            details_json=details,
            component="api"
        ) is not None

    @staticmethod
    def log_provider_switched(
        message_id: str,
        original_provider: str,
        new_provider: str,
        reason: str
    ) -> bool:
        """Registra cambio de proveedor"""
        
        details = {
            "original_provider": original_provider,
            "new_provider": new_provider,
            "switch_reason": reason,
            "switched_at": datetime.utcnow().isoformat()
        }
        
        return DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="provider_switched",
            event_status="updated",
            event_message=f"Provider switched from {original_provider} to {new_provider}: {reason}",
            details_json=details,
            component="celery",
            provider=new_provider
        ) is not None

    @staticmethod
    def create_audit_context(message_id: str):
        """Crea contexto de auditoría con timing automático"""
        return AuditContext(message_id)


class AuditContext:
    """Contexto para medir tiempo de operaciones"""
    
    def __init__(self, message_id: str):
        self.message_id = message_id
        self.start_time = None
        self.operation_name = None
    
    def start_operation(self, operation_name: str):
        """Inicia medición de una operación"""
        self.operation_name = operation_name
        self.start_time = time.time()
        return self
    
    def finish_operation(self, status: str = "success", details: Optional[Dict[str, Any]] = None):
        """Finaliza medición y registra el evento"""
        if self.start_time is None:
            return False
        
        processing_time_ms = int((time.time() - self.start_time) * 1000)
        
        return DatabaseService.add_notification_log(
            message_id=self.message_id,
            event_type=f"operation_{self.operation_name}",
            event_status=status,
            event_message=f"Operation {self.operation_name} completed in {processing_time_ms}ms",
            details_json=details or {},
            component="system",
            processing_time_ms=processing_time_ms
        ) is not None