# services/twilio_sms_sender.py
"""
Provider Twilio SMS - Envío de mensajes SMS texto plano
Implementa interfaz estándar de providers para integración con Celery tasks
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from twilio.base.exceptions import TwilioException

from .twilio_service import TwilioService
from constants import SMS_MAX_LENGTH


class TwilioSMSSender:
    """
    Provider para envío de SMS via Twilio
    """
    
    def __init__(self):
        self.provider_name = "twilio_sms"
        self.service = TwilioService(self.provider_name)
        
    async def send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía SMS via Twilio
        
        Args:
            payload: Datos del mensaje con to, body_text, message_id, etc.
            
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
            to_number = self.service.validate_phone_number(payload['to'])
            from_number = self.service.get_from_number('sms')
            body_text = payload.get('body_text', '')
            
            # Validar longitud del mensaje
            if len(body_text) > SMS_MAX_LENGTH:
                return self._error_response(
                    "message_too_long", 
                    f"SMS body exceeds {SMS_MAX_LENGTH} characters",
                    message_id
                )
                
            logging.info(f"Sending SMS via Twilio - Message: {message_id}, To: {to_number[:8]}...")
            
            # Enviar SMS via Twilio
            message = self.service.client.messages.create(
                body=body_text,
                from_=from_number,
                to=to_number
            )
            
            # Procesar respuesta exitosa
            result = {
                "success": True,
                "status": "sent",
                "message": "SMS sent successfully",
                "provider_message_id": message.sid,
                "provider_status": message.status,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            logging.info(f"SMS sent successfully - Message: {message_id}, Twilio SID: {message.sid}")
            return result
            
        except TwilioException as e:
            # Manejo específico de errores Twilio
            return self.service.handle_twilio_error(e, message_id)
            
        except Exception as e:
            # Manejo de errores generales
            logging.error(f"Unexpected error sending SMS {message_id}: {e}")
            return self._error_response(
                "internal_error",
                f"Unexpected error: {str(e)}",
                message_id
            )
            
    def _validate_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida payload específico para SMS
        """
        # Campo 'to' requerido
        if not payload.get('to'):
            return {"valid": False, "error": "Missing 'to' field"}
            
        # Debe tener body_text para SMS
        if not payload.get('body_text'):
            return {"valid": False, "error": "Missing 'body_text' field for SMS"}
            
        # No debe tener media en SMS
        if payload.get('media'):
            return {"valid": False, "error": "SMS does not support media attachments"}
            
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
        Consulta estado de mensaje SMS enviado
        
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
                'received': 'delivered',
                'delivered': 'delivered',
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
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
        except TwilioException as e:
            logging.error(f"Error fetching SMS status {provider_message_id}: {e}")
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
            "provider_type": "sms",
            "channel": "sms",
            "supports_media": False,
            "max_message_length": SMS_MAX_LENGTH
        })
        return base_info
        
    async def test_connection(self) -> Dict[str, Any]:
        """
        Prueba conexión al servicio Twilio
        """
        try:
            # Test básico: obtener info de cuenta
            account = self.service.client.api.accounts(self.service.config['account_sid']).fetch()
            
            return {
                "success": True,
                "provider": self.provider_name,
                "status": "connected",
                "account": account.friendly_name,
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