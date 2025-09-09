"""
Test endpoints - Validación y pruebas del sistema de notificaciones
"""

import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from constants import (
    HTTP_202_ACCEPTED, HTTP_400_BAD_REQUEST, TEST_RECIPIENTS, HTTP_404_NOT_FOUND
)
from models.test_request import TestRequest, TestResponse, ConnectivityTestResponse
from utils.redis_client import get_redis_client
from utils.config_loader import load_providers_config
from services.celery_tasks import send_test_notification_task
from services.smtp_test import test_smtp_connectivity

router = APIRouter()


@router.post("/test/send", response_model=TestResponse, status_code=HTTP_202_ACCEPTED)
async def send_test_notification(
    test_request: TestRequest,
    redis_client = Depends(get_redis_client)
):
    """
    Envía una notificación de prueba usando una configuración específica
    
    Permite probar:
    - Conectividad con proveedores SMTP/API
    - Renderizado de templates
    - Configuración de routing
    - Pipeline completo de envío
    """
    
    message_id = str(uuid.uuid4())
    
    try:
        # Cargar configuración de proveedores
        providers_config = load_providers_config()
        
        # Validar que el proveedor existe
        if test_request.provider not in providers_config:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_provider",
                    "message": f"Provider '{test_request.provider}' not found in configuration"
                }
            )
        
        # Usar destinatarios de prueba si no se especifican
        test_recipients = test_request.to or TEST_RECIPIENTS
        
        # Preparar payload de prueba
        test_payload = {
            "message_id": message_id,
            "request_id": f"test-{message_id}",
            "to": test_recipients,
            "cc": test_request.cc,
            "bcc": test_request.bcc,
            "subject": test_request.subject or "Test Notification - Notify API",
            "template_id": test_request.template_id,
            "body_text": test_request.body_text or "This is a test notification from Notify API system.",
            "body_html": test_request.body_html or "<p>This is a <strong>test notification</strong> from Notify API system.</p>",
            "vars": test_request.vars or {},
            "provider": test_request.provider,
            "is_test": True,  # Flag para identificar como test
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Encolar tarea de prueba en Celery
        celery_task = send_test_notification_task.delay(test_payload)
        
        # Preparar respuesta
        response = TestResponse(
            test_id=message_id,
            status="accepted",
            celery_task_id=celery_task.id,
            provider=test_request.provider,
            recipients=test_recipients,
            message="Test notification queued successfully"
        )
        
        # Log estructurado
        logging.info(
            "Test notification queued",
            extra={
                "test_id": message_id,
                "celery_task_id": celery_task.id,
                "provider": test_request.provider,
                "recipients": len(test_recipients),
                "has_template": bool(test_request.template_id)
            }
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Test notification failed: {e}", extra={
            "test_id": message_id,
            "provider": test_request.provider,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "test_failed",
                "message": "Failed to queue test notification"
            }
        )


@router.get("/test/connectivity", response_model=ConnectivityTestResponse)
async def test_connectivity(
    provider: Optional[str] = Query(None, description="Specific provider to test (optional)"),
    timeout: int = Query(default=10, ge=1, le=60, description="Connection timeout in seconds")
):
    """
    Prueba la conectividad con proveedores de correo sin enviar mensajes
    
    Verifica:
    - Conexión SMTP/API
    - Autenticación
    - Configuración válida
    - Tiempos de respuesta
    """
    
    try:
        # Cargar configuración de proveedores
        providers_config = load_providers_config()
        
        if not providers_config:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail={
                    "error": "no_providers",
                    "message": "No providers configured"
                }
            )
        
        # Determinar qué proveedores probar
        providers_to_test = [provider] if provider else list(providers_config.keys())
        
        # Validar proveedor específico si se solicita
        if provider and provider not in providers_config:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_provider",
                    "message": f"Provider '{provider}' not found in configuration"
                }
            )
        
        # Probar conectividad de cada proveedor
        connectivity_results = {}
        overall_status = "healthy"
        
        for provider_name in providers_to_test:
            provider_config = providers_config[provider_name]
            
            try:
                # Probar conectividad específica según tipo de proveedor
                if provider_config.get("type") == "smtp":
                    result = await test_smtp_connectivity(provider_config, timeout)
                elif provider_config.get("type") == "api":
                    # TODO: Implementar test para proveedores API (SES, SendGrid, etc.)
                    result = {
                        "status": "not_implemented",
                        "message": "API provider testing not implemented yet",
                        "response_time": 0
                    }
                else:
                    result = {
                        "status": "error",
                        "message": f"Unknown provider type: {provider_config.get('type')}",
                        "response_time": 0
                    }
                
                connectivity_results[provider_name] = result
                
                # Actualizar estado general
                if result["status"] != "healthy":
                    overall_status = "degraded"
                    
            except Exception as e:
                connectivity_results[provider_name] = {
                    "status": "error",
                    "message": str(e),
                    "response_time": 0
                }
                overall_status = "degraded"
                logging.error(f"Connectivity test failed for {provider_name}: {e}")
        
        response = ConnectivityTestResponse(
            overall_status=overall_status,
            providers_tested=len(providers_to_test),
            results=connectivity_results,
            tested_at=datetime.utcnow().isoformat()
        )
        
        logging.info(f"Connectivity test completed: {overall_status}", extra={
            "providers_tested": len(providers_to_test),
            "overall_status": overall_status
        })
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Connectivity test failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "connectivity_test_failed",
                "message": "Failed to perform connectivity test"
            }
        )


@router.get("/test/templates")
async def list_available_templates():
    """
    Lista las plantillas disponibles para testing
    """
    
    try:
        from utils.template_loader import get_available_templates
        
        templates = get_available_templates()
        
        return {
            "templates": templates,
            "count": len(templates),
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Failed to list templates: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "template_listing_failed",
                "message": "Failed to retrieve available templates"
            }
        )


@router.post("/test/template/{template_id}")
async def test_template_rendering(
    template_id: str,
    template_vars: dict = {}
):
    """
    Prueba el renderizado de una plantilla específica sin enviar correo
    """
    
    try:
        from services.template_renderer import render_template
        
        # Renderizar plantilla con variables de prueba
        rendered = await render_template(
            template_id=template_id,
            variables=template_vars or {"test_var": "test_value", "user_name": "Test User"}
        )
        
        return {
            "template_id": template_id,
            "variables_used": template_vars or {"test_var": "test_value", "user_name": "Test User"},
            "rendered": {
                "subject": rendered.get("subject"),
                "body_text": rendered.get("body_text"),
                "body_html": rendered.get("body_html")
            },
            "rendered_at": datetime.utcnow().isoformat()
        }
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail={
                "error": "template_not_found",
                "message": f"Template '{template_id}' not found"
            }
        )
    except Exception as e:
        logging.error(f"Template rendering test failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "template_rendering_failed",
                "message": "Failed to render template"
            }
        )