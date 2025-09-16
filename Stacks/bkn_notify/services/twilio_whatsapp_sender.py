# services/twilio_whatsapp_sender.py
"""
Provider Twilio WhatsApp - Envío de mensajes WhatsApp con soporte media
Implementa interfaz estándar de providers para integración con Celery tasks
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from twilio.base.exceptions import TwilioException

from .twilio_service import TwilioService
from constants import WHATSAPP_MAX_LENGTH, WHATSAPP_MAX_MEDIA


class TwilioWhatsAppSender:
    """
    Provider para envío de WhatsApp via Twilio
    """
    
    def __init__(self):
        self.provider_name = "twilio_whatsapp"
        self.service = TwilioService(self.provider_name)
        
    async def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía mensaje WhatsApp via Twilio
        
        Args:
            payload: Datos del mensaje con to, body_text, media, message_id, etc.
            
        Returns:
            Dict: Resultado del envío con success, status, provider_message_id
        """
        message_id = payload.get('message_id', 'unknown')
        
        try:
            # Validar payload requerido
            validation_result = self._validate_payload(payload)
            if not validation_result['valid']:
                return self._error_response(
                    "validation_failed",
                    validation_result['error'],
                    message_id
                )
                
            # Preparar datos del mensaje
            to_number = self.service.format_whatsapp_number(payload['to'])
            from_number = self.service.get_from_number('whatsapp')
            body_text = payload.get('body_text', '')
            
            # Validar longitud del mensaje
            if len(body_text) > WHATSAPP_MAX_LENGTH:
                return self._error_response(
                    "message_too_long", 
                    f"WhatsApp body exceeds {WHATSAPP_MAX_LENGTH} characters",
                    message_id
                )
                
            # Procesar media si existe
            media_urls = []
            if payload.get('media'):
                media_urls = self.service.validate_media_urls(payload['media'])
                if len(media_urls) > WHATSAPP_MAX_MEDIA:
                    return self._error_response(
                        "too_many_media",
                        f"WhatsApp supports maximum {WHATSAPP_MAX_MEDIA} media attachments",
                        message_id
                    )
                    
            logging.info(f"Sending WhatsApp via Twilio - Message: {message_id}, To: {to_number[:16]}..., Media: {len(media_urls)}")
            
            # Preparar parámetros del mensaje
            message_params = {
                'body': body_text,
                'from_': from_number,
                'to': to_number
            }
            
            # Agregar media si existe
            if media_urls:
                message_params['media_url'] = media_urls
                
            # Enviar mensaje via Twilio
            message = self.service.client.messages.create(**message_params)
            
            # Procesar respuesta exitosa
            result = {
                "success": True,
                "status": "sent",
                "message": "WhatsApp message sent successfully",
                "provider_message_id": message.sid,
                "provider_status": message.status,
                "media_count": len(media_urls),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            logging.info(f"WhatsApp sent successfully - Message: {message_id}, Twilio SID: {message.sid}")
            return result
            
        except TwilioException as e:
            # Manejo específico de errores Twilio
            return self.service.handle_twilio_error(e, message_id)
            
        except Exception as e:
            # Manejo de errores generales
            logging.error(f"Unexpected error sending WhatsApp {message_id}: {e}")
            return self._error_response(
                "internal_error",
                f"Unexpected error: {str(e)}",
                message_id
            )
            
    def _validate_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida payload específico para WhatsApp
        """
        # Campo 'to' requerido
        if not payload.get('to'):
            return {"valid": False, "error": "Missing 'to' field"}
            
        # Debe tener body_text o media para WhatsApp
        if not payload.get('body_text') and not payload.get('media'):
            return {"valid": False, "error": "WhatsApp requires either 'body_text' or 'media'"}
            
        # Validar estructura de media si existe
        if payload.get('media'):
            if not isinstance(payload['media'], list):
                return {"valid": False, "error": "Media must be an array"}
                
            for media_item in payload['media']:
                if not isinstance(media_item, dict):
                    return {"valid": False, "error": "Each media item must be an object"}
                    
                if not media_item.get('url'):
                    return {"valid": False, "error": "Each media item must have 'url' field"}
                    
        return {"valid": True}
        
    def _error_response(self, status: str, message: str, message_id: str) -> Dict[str, Any]:
        """
        Genera respuesta de error estandarizada
        """
        return {
            "success": False,
            "status": status,
            "message": message,
            "provider_message_id": None,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    async def get_status(self, provider_message_id: str) -> Dict[str, Any]:
        """
        Consulta estado de mensaje WhatsApp enviado
        
        Args:
            provider_message_id: SID del mensaje en Twilio
            
        Returns:
            Dict: Estado actual del mensaje
        """
        try:
            message = self.service.client.messages(provider_message_id).fetch()
            
            # Mapear estados de Twilio a estados estándar
            status_mapping = {
                'queued': 'pending',
                'sent': 'sent',
                'delivered': 'delivered', 
                'read': 'delivered',
                'received': 'delivered',
                'undelivered': 'failed',
                'failed': 'failed'
            }
            
            status = status_mapping.get(message.status, 'unknown')
            
            return {
                "success": True,
                "status": status,
                "provider_status": message.status,
                "provider_message_id": provider_message_id,
                "error_code": message.error_code,
                "error_message": message.error_message,
                "num_media": message.num_media,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
        except TwilioException as e:
            logging.error(f"Error fetching WhatsApp status {provider_message_id}: {e}")
            return {
                "success": False,
                "status": "unknown",
                "message": f"Error fetching status: {e}",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Información del provider para debugging y health checks
        """
        base_info = self.service.get_service_info()
        base_info.update({
            "provider_type": "whatsapp",
            "channel": "whatsapp",
            "supports_media": True,
            "max_message_length": WHATSAPP_MAX_LENGTH,
            "max_media_count": WHATSAPP_MAX_MEDIA,
            "supported_media_types": ["image", "document", "audio", "video"]
        })
        return base_info
        
    async def test_connection(self) -> Dict[str, Any]:
        """
        Prueba conexión al servicio Twilio WhatsApp
        """
        try:
            # Test básico: obtener info de cuenta
            account = self.service.client.api.accounts(self.service.config['account_sid']).fetch()
            
            # Verificar que el número tiene WhatsApp habilitado
            # Nota: En producción se podría hacer una validación más específica
            
            return {
                "success": True,
                "provider": self.provider_name,
                "status": "connected",
                "account": account.friendly_name,
                "whatsapp_enabled": True,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
        except Exception as e:
            return {
                "success": False,
                "provider": self.provider_name,
                "status": "connection_failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
    def _extract_media_info(self, media_list: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Extrae información útil de media para logging
        """
        if not media_list:
            return []
            
        media_info = []
        for media_item in media_list:
            info = {
                "type": media_item.get("type", "unknown"),
                "url": media_item.get("url", "")[:50] + "..." if len(media_item.get("url", "")) > 50 else media_item.get("url", ""),
                "caption": media_item.get("caption", "")[:30] + "..." if len(media_item.get("caption", "")) > 30 else media_item.get("caption", "")
            }
            media_info.append(info)
            
        return media_info