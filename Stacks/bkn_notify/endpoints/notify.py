"""
Notify endpoint - Core del sistema de notificaciones
"""

import uuid
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
from services.celery_tasks import send_notification_task
from services.database_service import DatabaseService

router = APIRouter()


@router.post("/notify", response_model=NotifyResponse, status_code=HTTP_202_ACCEPTED)
async def send_notification(
    request: NotifyRequest,
    http_request: Request,
    redis_client = Depends(get_redis_client)
):
    """
    Envía una notificación por correo electrónico
    
    - Valida el payload
    - Aplica políticas de routing y whitelist
    - Maneja idempotencia
    - Registra en MySQL
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
        
        # Preparar payload para Celery
        task_payload = {
            "message_id": message_id,
            "request_id": request_id,
            "to": request.to,
            "cc": request.cc,
            "bcc": request.bcc,
            "subject": request.subject,
            "template_id": request.template_id,
            "body_text": request.body_text,
            "body_html": request.body_html,
            "vars": request.vars,
            "attachments": request.attachments,
            "provider": routing_config.get("provider"),
            "routing_hint": request.routing_hint,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # NUEVO: Registrar notificación en MySQL - TODOS LOS CAMPOS
        try:
            # Obtener información adicional del request HTTP
            source_ip = http_request.client.host if http_request.client else None
            user_agent = http_request.headers.get("user-agent")
            api_key = http_request.headers.get("X-API-Key")
            
            # Hash de API key para auditoría
            api_key_hash = None
            if api_key:
                import hashlib
                api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            
            # Preparar destinatarios como JSON
            to_emails_json = request.to if isinstance(request.to, list) else [request.to]
            cc_emails_json = request.cc if request.cc else None
            bcc_emails_json = request.bcc if request.bcc else None
            
            # Crear registro con TODOS los campos requeridos
            db_notification = DatabaseService.create_notification(
                message_id=message_id,
                
                # Destinatarios
                to_email=str(to_emails_json[0]) if to_emails_json else "",
                cc_emails=cc_emails_json,
                bcc_emails=bcc_emails_json,
                
                # Contenido - CAMPOS QUE FALTABAN
                subject=request.subject,                    # ✅ AGREGADO
                body_text=request.body_text,               # ✅ AGREGADO
                # body_html no se guarda como solicitaste
                
                # Template info  
                template_id=request.template_id,
                params_json=request.vars,
                
                # Configuración - CAMPOS QUE FALTABAN  
                provider=routing_config.get("provider"),
                routing_hint=request.routing_hint,         # ✅ AGREGADO
                priority=getattr(request, 'priority', 'medium'),
                
                # Metadatos - CAMPOS QUE FALTABAN
                idempotency_key=idempotency_key,           # ✅ AGREGADO
                source_ip=source_ip,
                user_agent=user_agent,
                api_key_hash=api_key_hash
            )
            
            if db_notification:
                logging.debug(f"Notification {message_id} registered with ALL fields")
            else:
                logging.warning(f"Failed to register notification {message_id}")
                
        except Exception as db_error:
            logging.error(f"Database error for {message_id}: {db_error}", exc_info=True)
        
        # Encolar tarea en Celery
        celery_task = send_notification_task.delay(task_payload)
        
        # NUEVO: Actualizar BD con task ID - CAMPO QUE FALTABA
        try:
            DatabaseService.update_notification_status(
                message_id=message_id,
                status="processing",                        # ✅ CAMBIARÁ DE pending
                celery_task_id=celery_task.id              # ✅ AGREGADO
            )
            logging.debug(f"Updated {message_id} to processing with task {celery_task.id}")
        except Exception as db_error:
            logging.error(f"Failed to update task ID for {message_id}: {db_error}")
        
        # Preparar respuesta
        response_data = NotifyResponse(
            message_id=message_id,
            status="accepted",
            celery_task_id=celery_task.id,
            provider=routing_config.get("provider"),
            estimated_delivery="immediate"
        )
        
        # Guardar en cache de idempotencia si se especificó
        if idempotency_key:
            await cache_idempotent_response(
                redis_client, idempotency_key, response_data
            )
        
        # Log estructurado
        logging.info(
            "Notification request accepted",
            extra={
                "message_id": message_id,
                "request_id": request_id,
                "celery_task_id": celery_task.id,
                "provider": routing_config.get("provider"),
                "recipients": len(request.to),
                "has_template": bool(request.template_id),
                "idempotency_key": idempotency_key
            }
        )
        
        return response_data
        
    except ValueError as e:
        # Errores de validación de políticas
        logging.warning(f"Policy validation failed: {e}", extra={
            "message_id": message_id,
            "request_id": request_id,
            "error": str(e)
        })
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail={"error": "policy_violation", "message": str(e)}
        )
        
    except Exception as e:
        # Errores inesperados
        logging.error(f"Notification request failed: {e}", extra={
            "message_id": message_id,
            "request_id": request_id,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "Failed to process notification"}
        )


async def handle_idempotency(redis_client, idempotency_key: str, message_id: str):
    """
    Maneja la lógica de idempotencia usando Redis
    """
    cache_key = f"{REDIS_IDEMPOTENCY_PREFIX}{idempotency_key}"
    
    # Verificar si ya existe una respuesta cached
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        import json
        return NotifyResponse(**json.loads(cached_data))
    
    # Marcar como en proceso (para evitar duplicados concurrentes)
    processing_key = f"{cache_key}:processing"
    is_processing = await redis_client.set(
        processing_key, message_id, nx=True, ex=60  # 60 segundos
    )
    
    if not is_processing:
        # Otra request está procesando esta clave
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail={
                "error": "concurrent_request", 
                "message": "Another request with the same idempotency key is being processed"
            }
        )
    
    return None


async def cache_idempotent_response(redis_client, idempotency_key: str, response: NotifyResponse):
    """
    Guarda la respuesta en cache para futuras requests idempotentes
    """
    from constants import REDIS_TTL_IDEMPOTENCY
    import json
    
    cache_key = f"{REDIS_IDEMPOTENCY_PREFIX}{idempotency_key}"
    processing_key = f"{cache_key}:processing"
    
    # Guardar respuesta
    await redis_client.setex(
        cache_key, 
        REDIS_TTL_IDEMPOTENCY, 
        json.dumps(response.dict())
    )
    
    # Limpiar marca de procesamiento
    await redis_client.delete(processing_key)