"""
Notify endpoint - Core del sistema de notificaciones
CORREGIDO: Renderiza templates ANTES del registro en BD para completar todos los campos
"""

import uuid
import hashlib
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse

from constants import (
    HTTP_202_ACCEPTED, HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT,
    IDEMPOTENCY_HEADER, REQUEST_ID_HEADER, REDIS_IDEMPOTENCY_PREFIX
)
from models.notify_request import NotifyRequest, NotifyResponse
from utils.redis_client import get_redis_client
from utils.policy_validator import validate_request
from utils.routing_engine import apply_routing
from utils.template_loader import render_template
from services.celery_tasks import send_notification_task
from services.database_service import DatabaseService

router = APIRouter()


@router.post("/notify_mail", response_model=NotifyResponse, status_code=HTTP_202_ACCEPTED)
async def send_notification(
    request: NotifyRequest,
    http_request: Request,
    redis_client = Depends(get_redis_client)
):
    """
    Envía una notificación por correo electrónico
    
    - Valida el payload
    - Renderiza template SI se usa template_id
    - Aplica políticas de routing y whitelist
    - Maneja idempotencia
    - Registra en MySQL con TODOS los campos completos
    - Encola tarea en Celery
    - Retorna message_id para seguimiento
    """
    
    # Generar IDs únicos
    message_id = str(uuid.uuid4())
    request_id = getattr(http_request.state, 'request_id', str(uuid.uuid4()))
    
    # Obtener clave de idempotencia si existe
    idempotency_key = http_request.headers.get(IDEMPOTENCY_HEADER)
    
    try:
        # Manejar idempotencia
        if idempotency_key:
            cached_response = await handle_idempotency(
                redis_client, idempotency_key, message_id
            )
            if cached_response:
                logging.info(f"Idempotent request returned cached response: {idempotency_key}")
                return cached_response
        
        # Validar políticas (whitelist, límites, etc.)
        await validate_request(request)
        
        # Aplicar reglas de routing
        routing_config = await apply_routing(request)
        
        # ✅ NUEVO: Renderizar template ANTES del registro si se usa template_id
        final_subject = request.subject
        final_body_text = request.body_text
        final_body_html = "N/A"
        
        if request.template_id:
            try:
                logging.info(f"Rendering template {request.template_id} before database registration")
                
                # Renderizar template con variables
                rendered_content = render_template(request.template_id, request.vars or {})
                
                # Usar contenido renderizado
                final_subject = rendered_content.get("subject", "")
                final_body_text = rendered_content.get("body_text", "")  
                # final_body_html = rendered_content.get("body_html", "")
                
                logging.info(f"Template rendered successfully: subject_len={len(final_subject)}, text_len={len(final_body_text)}, html_len={len(final_body_html)}")
                
            except Exception as e:
                logging.error(f"Template rendering failed for {request.template_id}: {e}")
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail=f"Template rendering failed: {str(e)}"
                )
        
        # ✅ CORREGIDO: Procesar template_version de forma consistente
        template_version = None
        if request.template_id:
            # Normalizar formato: siempre usar / como separador
            if '/' in request.template_id:
                parts = request.template_id.split('/', 2)
                if len(parts) >= 2:
                    template_version = parts[1]  # Extraer versión después del /
            elif '.' in request.template_id:
                parts = request.template_id.split('.', 2)
                if len(parts) >= 2:
                    template_version = parts[1]  # Extraer versión después del .
            else:
                template_version = "v1"  # Versión por defecto
        
        # Registrar notificación en MySQL con TODOS los campos completos
        try:
            # Obtener información adicional del request HTTP
            source_ip = http_request.client.host if http_request.client else None
            user_agent = http_request.headers.get("user-agent")
            api_key = http_request.headers.get("X-API-Key")
            
            # Hash de API key para auditoría
            api_key_hash = None
            if api_key:
                api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            
            # Preparar destinatarios como JSON
            to_emails_json = request.to if isinstance(request.to, list) else [request.to]
            cc_emails_json = request.cc if request.cc else None
            bcc_emails_json = request.bcc if request.bcc else None
            
            logging.info(f"Registering notification in database: {message_id}")
            
            # ✅ CORREGIDO: Registrar con contenido completo (renderizado si usa template)
            db_notification = DatabaseService.create_notification(
                message_id=message_id,
                
                # Destinatarios
                to_email=str(to_emails_json[0]) if to_emails_json else "",
                cc_emails=cc_emails_json,
                bcc_emails=bcc_emails_json,
                
                # ✅ CORREGIDO: Contenido COMPLETO (renderizado o directo)
                subject=final_subject,
                body_text=final_body_text,
                body_html=final_body_html,
                
                # Template info  
                template_id=request.template_id,
                template_version=template_version,
                
                params_json=request.vars,
                
                # Configuración de envío
                provider=routing_config.get("provider"),
                routing_hint=request.routing_hint,
                priority=getattr(request, 'priority', 'MEDIUM'),
                
                # Metadatos de idempotencia y Celery
                idempotency_key=idempotency_key,
                # celery_task_id se asignará después del enqueue
                
                # Metadatos de auditoría
                source_ip=source_ip,
                user_agent=user_agent,
                api_key_hash=api_key_hash
            )
            
            if not db_notification:
                logging.error(f"Failed to create notification record: {message_id}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to register notification"
                )
                
            logging.info(f"Notification registered successfully: {message_id}")
            
        except Exception as db_error:
            logging.error(f"Database registration error for {message_id}: {db_error}")
            # Continuar con el envío aunque falle el registro
            # En producción podrías decidir fallar aquí
            
        # Preparar payload para Celery con contenido ya renderizado
        task_payload = {
            "message_id": message_id,
            "request_id": request_id,
            "to": request.to,
            "cc": request.cc,
            "bcc": request.bcc,
            
            # ✅ CORREGIDO: Usar contenido ya renderizado para evitar doble renderizado
            "subject": final_subject,
            "template_id": request.template_id,
            "body_text": final_body_text,
            "body_html": final_body_html,
            "vars": request.vars,
            
            "attachments": request.attachments,
            "provider": routing_config.get("provider"),
            "routing_hint": request.routing_hint,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Encolar tarea en Celery
        celery_task = send_notification_task.delay(task_payload)
        celery_task_id = str(celery_task.id)
        
        # Actualizar el registro con el celery_task_id
        try:
            # ✅ CORREGIDO: Usar método existente update_notification_status
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="PROCESSING",  # Cambiar a processing cuando se encola
                celery_task_id=celery_task_id
            )
            logging.info(f"Updated notification with celery_task_id: {message_id} -> {celery_task_id}")
        except Exception as update_error:
            logging.error(f"Failed to update celery_task_id for {message_id}: {update_error}")
        
        # Guardar en cache de idempotencia si corresponde
        if idempotency_key:
            response_data = {
                "message_id": message_id,
                "request_id": request_id,
                "status": "accepted",
                "provider": routing_config.get("provider"),
                "celery_task_id": celery_task_id,
                "queued_at": datetime.utcnow().isoformat()
            }
            
            await cache_idempotent_response(redis_client, idempotency_key, response_data)
        
        # Respuesta exitosa
        return NotifyResponse(
            message_id=message_id,
            request_id=request_id,
            status="accepted",
            provider=routing_config.get("provider"),
            celery_task_id=celery_task_id,
            queued_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        # Re-lanzar HTTPExceptions sin modificar
        raise
        
    except Exception as e:
        logging.error(f"Unexpected error in notify endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing notification"
        )

@router.post("/notify_twilio", response_model=NotifyResponse, status_code=HTTP_202_ACCEPTED)
async def send_twilio_notification(
    request: NotifyRequest,
    http_request: Request,
    redis_client = Depends(get_redis_client)
):
    """
    Envía notificación vía Twilio (SMS o WhatsApp)
    """
    message_id = str(uuid.uuid4())
    request_id = getattr(http_request.state, 'request_id', str(uuid.uuid4()))
    idempotency_key = http_request.headers.get(IDEMPOTENCY_HEADER)

    # Manejar idempotencia
    if idempotency_key:
        cached = await handle_idempotency(redis_client, idempotency_key, message_id)
        if cached:
            return cached

    # Validar payload
    await validate_request(request)

    # Renderizar template si corresponde
    final_body_text = request.body_text
    if request.template_id:
        rendered = render_template(request.template_id, request.vars or {})
        final_body_text = rendered.get("body_text", "")

    # Determinar provider: sms o whatsapp
    if request.routing_hint == "whatsapp":
        provider = "twilio_whatsapp"
    else:
        provider = "twilio_sms"

    # Armar payload para Celery
    task_payload = {
        "message_id": message_id,
        "request_id": request_id,
        "to": request.to,
        "body_text": final_body_text,
        "provider": provider,
        "vars": request.vars,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Encolar en Celery
    celery_task = send_notification_task.delay(task_payload)
    celery_task_id = str(celery_task.id)

    # Guardar en BD (igual que en notify_mail)
    DatabaseService.create_notification(
        message_id=message_id,
        to_email=request.to,
        subject="",
        body_text=final_body_text,
        provider=provider,
        template_id=request.template_id,
        routing_hint=request.routing_hint,
        priority=request.priority,
        celery_task_id=celery_task_id,
        idempotency_key=idempotency_key
    )

    # Cache idempotente
    if idempotency_key:
        await cache_idempotent_response(redis_client, idempotency_key, {
            "message_id": message_id,
            "request_id": request_id,
            "status": "accepted",
            "provider": provider,
            "celery_task_id": celery_task_id,
            "queued_at": datetime.utcnow().isoformat()
        })

    return NotifyResponse(
        message_id=message_id,
        request_id=request_id,
        status="accepted",
        provider=provider,
        celery_task_id=celery_task_id,
        queued_at=datetime.utcnow().isoformat()
    )



async def handle_idempotency(redis_client, idempotency_key: str, message_id: str):
    """
    Maneja la idempotencia usando Redis
    """
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
    """
    Guarda respuesta en cache de idempotencia
    """
    try:
        import json
        cache_key = f"{REDIS_IDEMPOTENCY_PREFIX}:{idempotency_key}"
        
        # Cache por 24 horas
        await redis_client.setex(
            cache_key, 
            86400,  # 24 horas en segundos
            json.dumps(response_data)
        )
        
        logging.debug(f"Cached idempotent response: {idempotency_key}")
        
    except Exception as e:
        logging.warning(f"Failed to cache idempotent response {idempotency_key}: {e}")