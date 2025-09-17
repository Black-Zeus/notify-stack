"""
Notify endpoint - REFACTORIZADO con lógica común encapsulada
Elimina duplicación de código entre endpoints de email y Twilio
CON INTEGRACIÓN DE PROVIDER_STATS PARA RECHAZOS
"""

import uuid
import hashlib
import logging
from datetime import datetime
from typing import Union, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

from constants import (
    HTTP_202_ACCEPTED, HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT,
    IDEMPOTENCY_HEADER, REQUEST_ID_HEADER, REDIS_IDEMPOTENCY_PREFIX
)
from models.notify_request import NotifyRequest, NotifyResponse
from models.twilio_request import TwilioNotifyRequest
from utils.redis_client import get_redis_client
from utils.policy_validator import validate_request, NotificationRejectedError  # ✅ NUEVO IMPORT
from utils.routing_engine import apply_routing
from utils.template_loader import render_template
from utils.config_loader import load_providers_config
from services.celery_tasks import send_notification_task  # ✅ CORREGIDO: Solo importar la tarea
from services.database_service import DatabaseService

router = APIRouter()


# =============================================================================
# FUNCIONES COMUNES REFACTORIZADAS
# =============================================================================

def validate_provider_configuration(provider: str) -> dict:
    """
    Valida que el proveedor esté configurado y habilitado
    """
    try:
        providers_config = load_providers_config()
        
        if not providers_config:
            # ✅ NUEVO: Lanzar excepción específica para rechazos
            raise NotificationRejectedError(
                "No provider configurations found",
                "no_providers_configured",
                provider
            )
        
        if provider not in providers_config:
            raise NotificationRejectedError(
                f"Provider '{provider}' is not available or configured. Please contact your system administrator",
                "provider_not_found",
                provider
            )
        
        provider_config = providers_config[provider]
        
        if not provider_config.get("enabled", False):
            raise NotificationRejectedError(
                f"Provider '{provider}' is disabled. Please enable it in configuration or use another provider",
                "provider_disabled",
                provider
            )
        
        # Validar credenciales según el tipo
        provider_type = provider_config.get("type", "").lower()
        
        if provider_type == "smtp":
            required_fields = ["host", "port"]
            missing_fields = [field for field in required_fields if not provider_config.get(field)]
            if missing_fields:
                raise NotificationRejectedError(
                    f"Provider '{provider}' missing required SMTP fields: {missing_fields}",
                    "provider_missing_smtp_config",
                    provider
                )
                
        elif provider_type == "api":
            provider_subtype = provider_config.get("provider_type", "")
            
            if provider_subtype in ["twilio_sms", "twilio_whatsapp"]:
                required_fields = ["account_sid", "auth_token", "from_number"]
                missing_fields = [field for field in required_fields if not provider_config.get(field)]
                if missing_fields:
                    raise NotificationRejectedError(
                        f"Provider '{provider}' missing required Twilio fields: {missing_fields}",
                        "provider_missing_twilio_config",
                        provider
                    )
            else:
                required_fields = ["endpoint"]
                missing_fields = [field for field in required_fields if not provider_config.get(field)]
                if missing_fields:
                    raise NotificationRejectedError(
                        f"Provider '{provider}' missing required API fields: {missing_fields}",
                        "provider_missing_api_config",
                        provider
                    )
        
        logging.info(f"Provider '{provider}' validation successful")
        return provider_config
        
    except NotificationRejectedError:
        raise  # Re-raise rejection errors
    except Exception as e:
        logging.error(f"Provider validation error for '{provider}': {e}")
        raise NotificationRejectedError(
            f"Provider configuration validation failed: {str(e)}",
            "provider_validation_error",
            provider
        )


async def handle_idempotency(redis_client, idempotency_key: str, message_id: str):
    """Maneja la idempotencia usando Redis"""
    try:
        cache_key = f"{REDIS_IDEMPOTENCY_PREFIX}:{idempotency_key}"
        cached_response = await redis_client.get(cache_key)
        
        if cached_response:
            import json
            return json.loads(cached_response)
            
        return None
        
    except Exception as e:
        logging.warning(f"Idempotency check failed for {idempotency_key}: {e}")
        return None


async def cache_idempotent_response(redis_client, idempotency_key: str, response_data: dict):
    """Guarda respuesta en cache de idempotencia"""
    try:
        import json
        cache_key = f"{REDIS_IDEMPOTENCY_PREFIX}:{idempotency_key}"
        
        await redis_client.setex(
            cache_key, 
            86400,  # 24 horas en segundos
            json.dumps(response_data)
        )
        
        logging.debug(f"Cached idempotent response: {idempotency_key}")
        
    except Exception as e:
        logging.warning(f"Failed to cache idempotent response {idempotency_key}: {e}")


def extract_template_version(template_id: str) -> Optional[str]:
    """Extrae la versión del template_id"""
    if not template_id:
        return None
        
    if '/' in template_id:
        parts = template_id.split('/', 2)
        if len(parts) >= 2:
            return parts[1]
    elif '.' in template_id:
        parts = template_id.split('.', 2)
        if len(parts) >= 2:
            return parts[1]
    
    return "v1"


def get_request_metadata(http_request: Request) -> Dict[str, Any]:
    """Extrae metadatos comunes del request HTTP"""
    source_ip = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")
    api_key = http_request.headers.get("X-API-Key")
    
    api_key_hash = None
    if api_key:
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    
    return {
        "source_ip": source_ip,
        "user_agent": user_agent,
        "api_key_hash": api_key_hash
    }


# ✅ NUEVA FUNCIÓN: Manejo centralizado de rechazos
async def handle_notification_rejection(
    rejection_error: NotificationRejectedError,
    message_id: str,
    notification_type: str,
    processing_time_ms: int = 0
) -> HTTPException:
    """
    Maneja rechazos de notificaciones y actualiza estadísticas directamente
    """
    try:
        # ✅ ACTUALIZACIONES DIRECTAS en lugar de llamar función inexistente
        
        # Actualizar estado en MySQL
        DatabaseService.update_notification_status(
            message_id=message_id,
            status="rejected"
        )
        DatabaseService.add_notification_log(
            message_id=message_id,
            event_type="notification_rejected",
            event_status="rejected",
            event_message=f"{notification_type.title()} notification rejected: {rejection_error.rejection_reason}",
            component="policy_validator",
            provider=rejection_error.provider,
            processing_time_ms=processing_time_ms,
            details_json={
                "rejection_reason": rejection_error.rejection_reason,
                "notification_type": notification_type,
                "processing_time_ms": processing_time_ms
            }
        )
        
        # ✅ DIRECTO: Actualizar estadísticas de proveedor (REJECTED)
        DatabaseService.update_provider_stats(
            provider=rejection_error.provider,
            stat_type="rejected",
            processing_time_ms=processing_time_ms
        )
        
        logging.warning(f"Notification rejected: {rejection_error.rejection_reason}", extra={
            "message_id": message_id,
            "provider": rejection_error.provider,
            "notification_type": notification_type,
            "rejection_reason": rejection_error.rejection_reason
        })
        
    except Exception as stats_error:
        logging.error(f"Failed to record rejection stats for {message_id}: {stats_error}")
    
    # Retornar HTTPException apropiado
    return HTTPException(
        status_code=HTTP_400_BAD_REQUEST,
        detail=str(rejection_error)
    )


async def process_notification_core(
    request: Union[NotifyRequest, TwilioNotifyRequest],
    http_request: Request,
    redis_client,
    notification_type: str  # "email" o "twilio"
) -> NotifyResponse:
    """
    LÓGICA CENTRAL común para ambos tipos de notificación
    CON MANEJO DE RECHAZOS Y ESTADÍSTICAS
    """
    # ✅ NUEVO: Tiempo de inicio para métricas
    start_time = datetime.utcnow()
    
    # 1. Generar IDs únicos
    message_id = str(uuid.uuid4())
    request_id = getattr(http_request.state, 'request_id', str(uuid.uuid4()))
    idempotency_key = http_request.headers.get(IDEMPOTENCY_HEADER)
    
    # 2. Manejar idempotencia
    if idempotency_key:
        cached_response = await handle_idempotency(redis_client, idempotency_key, message_id)
        if cached_response:
            logging.info(f"Idempotent {notification_type} request returned cached response: {idempotency_key}")
            return cached_response
    
    # ✅ NUEVO: Variables para tracking de provider
    provider = None
    provider_config = None
    
    try:
        # 3. Validaciones específicas por tipo
        if notification_type == "email":
            # Aplicar routing primero para obtener provider
            routing_config = await apply_routing(request)
            provider = routing_config.get("provider")
            
            # Validar políticas para email (ahora con provider para estadísticas)
            await validate_request(request, provider)
        else:  # twilio
            # Para Twilio, determinar provider directamente
            provider = request.provider
            if not provider:
                if request.routing_hint in ["urgent", "high_priority"]:
                    provider = "twilio_whatsapp"
                else:
                    provider = "twilio_sms"
            
            # Validar políticas para Twilio
            await validate_request(request, provider)
        
        # 4. Validar configuración del proveedor
        provider_config = validate_provider_configuration(provider)
        logging.info(f"{notification_type.title()} provider '{provider}' validated successfully")
        
    except NotificationRejectedError as rejection_error:
        # ✅ NUEVO: Manejo específico de rechazos
        processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        raise await handle_notification_rejection(
            rejection_error, message_id, notification_type, processing_time_ms
        )
    
    # 5. Renderizar template si existe
    final_subject = getattr(request, 'subject', "")
    final_body_text = request.body_text
    final_body_html = getattr(request, 'body_html', "")
    
    if request.template_id:
        try:
            logging.info(f"Rendering {notification_type} template {request.template_id}")
            rendered_content = render_template(request.template_id, request.vars or {})
            
            if notification_type == "email":
                final_subject = rendered_content.get("subject", "")
                final_body_text = rendered_content.get("body_text", "")
                final_body_html = rendered_content.get("body_html", "")
            else:  # twilio
                final_body_text = rendered_content.get("body_text", "")
                
            logging.info(f"{notification_type.title()} template rendered successfully")
            
        except Exception as e:
            logging.error(f"{notification_type.title()} template rendering failed for {request.template_id}: {e}")
            # ✅ NUEVO: Manejar error de template como rechazo
            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            template_rejection = NotificationRejectedError(
                f"Template rendering failed: {str(e)}",
                "template_render_error",
                provider
            )
            raise await handle_notification_rejection(
                template_rejection, message_id, notification_type, processing_time_ms
            )
    
    # 6. Registrar en base de datos
    try:
        metadata = get_request_metadata(http_request)
        template_version = extract_template_version(request.template_id)
        
        # Preparar datos según el tipo
        if notification_type == "email":
            to_emails_json = request.to if isinstance(request.to, list) else [request.to]
            primary_recipient = str(to_emails_json[0]) if to_emails_json else ""
            cc_emails = request.cc if request.cc else None
            bcc_emails = request.bcc if request.bcc else None
        else:  # twilio
            to_phone_list = request.to
            primary_recipient = to_phone_list[0] if to_phone_list else ""
            cc_emails = None
            bcc_emails = None
        
        logging.info(f"Registering {notification_type} notification in database: {message_id}")
        
        db_notification = DatabaseService.create_notification(
            message_id=message_id,
            to_email=primary_recipient,
            cc_emails=cc_emails,
            bcc_emails=bcc_emails,
            subject=final_subject,
            body_text=final_body_text,
            # body_html=final_body_html,
            body_html="N/A",
            template_id=request.template_id,
            template_version=template_version,
            params_json=request.vars,
            provider=provider,
            routing_hint=request.routing_hint,
            priority=getattr(request, 'priority', 'MEDIUM'),
            idempotency_key=idempotency_key,
            source_ip=metadata["source_ip"],
            user_agent=metadata["user_agent"],
            api_key_hash=metadata["api_key_hash"]
        )
        
        if not db_notification:
            logging.error(f"Failed to create {notification_type} notification record: {message_id}")
            # ✅ NUEVO: Manejar error de DB como rechazo
            processing_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            db_rejection = NotificationRejectedError(
                "Failed to register notification",
                "database_error",
                provider
            )
            raise await handle_notification_rejection(
                db_rejection, message_id, notification_type, processing_time_ms
            )
            
        logging.info(f"{notification_type.title()} notification registered successfully: {message_id}")
        
    except NotificationRejectedError:
        raise  # Re-raise rejection errors
    except Exception as db_error:
        logging.error(f"{notification_type.title()} database registration error for {message_id}: {db_error}")
        # Continuar con el envío aunque falle el registro
    
    # 7. Preparar payload para Celery
    if notification_type == "email":
        task_payload = {
            "message_id": message_id,
            "request_id": request_id,
            "to": request.to,
            "cc": request.cc,
            "bcc": request.bcc,
            "subject": final_subject,
            "template_id": request.template_id,
            "body_text": final_body_text,
            "body_html": final_body_html,
            "vars": request.vars,
            "attachments": request.attachments,
            "provider": provider,
            "routing_hint": request.routing_hint,
            "timestamp": datetime.utcnow().isoformat()
        }
    else:  # twilio
        task_payload = {
            "message_id": message_id,
            "request_id": request_id,
            "to": request.to,
            "body_text": final_body_text,
            "provider": provider,
            "template_id": request.template_id,
            "vars": request.vars,
            "routing_hint": request.routing_hint,
            "custom_options": getattr(request, 'custom_options', None),
            "timestamp": datetime.utcnow().isoformat(),
            "notification_type": "twilio"
        }
    
    # 8. Encolar tarea en Celery
    celery_task = send_notification_task.delay(task_payload)
    celery_task_id = str(celery_task.id)
    
    logging.info(f"{notification_type.title()} notification queued: {message_id} -> {celery_task_id}")
    
    # 9. Actualizar registro con celery_task_id
    try:
        DatabaseService.update_notification_status(
            message_id=message_id,
            status="PROCESSING",
            celery_task_id=celery_task_id
        )
        logging.info(f"Updated {notification_type} notification with celery_task_id: {message_id} -> {celery_task_id}")
    except Exception as update_error:
        logging.error(f"Failed to update {notification_type} celery_task_id for {message_id}: {update_error}")
    
    # 10. Cache de idempotencia
    if idempotency_key:
        response_data = {
            "message_id": message_id,
            "request_id": request_id,
            "status": "accepted",
            "provider": provider,
            "celery_task_id": celery_task_id,
            "notification_type": notification_type,
            "queued_at": datetime.utcnow().isoformat()
        }
        
        if notification_type == "twilio":
            response_data["recipient_count"] = len(request.to)
            
        await cache_idempotent_response(redis_client, idempotency_key, response_data)
    
    # 11. Retornar respuesta
    return NotifyResponse(
        message_id=message_id,
        request_id=request_id,
        status="accepted",
        provider=provider,
        celery_task_id=celery_task_id,
        queued_at=datetime.utcnow().isoformat()
    )


# =============================================================================
# ENDPOINTS SIMPLIFICADOS CON MANEJO DE RECHAZOS
# =============================================================================

@router.post("/notify_mail", response_model=NotifyResponse, status_code=HTTP_202_ACCEPTED)
async def send_notification(
    request: NotifyRequest,
    http_request: Request,
    redis_client = Depends(get_redis_client)
):
    """
    Envía notificación por correo electrónico - CON MANEJO DE RECHAZOS
    """
    try:
        return await process_notification_core(
            request=request,
            http_request=http_request,
            redis_client=redis_client,
            notification_type="email"
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions (including rejection errors)
        
    except Exception as e:
        logging.error(f"Unexpected error in email notify endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing email notification"
        )


@router.post("/notify_twilio", response_model=NotifyResponse, status_code=HTTP_202_ACCEPTED)
async def send_twilio_notification(
    request: TwilioNotifyRequest,
    http_request: Request,
    redis_client = Depends(get_redis_client)
):
    """
    Envía notificación vía Twilio (SMS/WhatsApp) - CON MANEJO DE RECHAZOS
    """
    try:
        return await process_notification_core(
            request=request,
            http_request=http_request,
            redis_client=redis_client,
            notification_type="twilio"
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions (including rejection errors)
        
    except Exception as e:
        logging.error(f"Unexpected error in Twilio notify endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing Twilio notification"
        )