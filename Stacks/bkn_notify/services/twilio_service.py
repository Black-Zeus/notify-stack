"""
Twilio Service - SMS y WhatsApp Business API
Manejo de envíos via Twilio para canales SMS y WhatsApp
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioRestException
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logging.warning("Twilio library not available - SMS/WhatsApp features disabled")

from constants import SMTP_TIMEOUT


class TwilioService:
    """
    Cliente para envío de SMS y WhatsApp via Twilio API
    """
    
    def __init__(self, provider_config: Dict[str, Any] = None):
        """
        Inicializa servicio Twilio con configuración
        """
        if not TWILIO_AVAILABLE:
            raise ImportError("twilio library is required for SMS/WhatsApp functionality")
        
        # Cargar configuración
        self.config = provider_config or {}
        
        # Credenciales Twilio
        self.account_sid = self.config.get('account_sid') or os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = self.config.get('auth_token') or os.getenv('TWILIO_AUTH_TOKEN')
        
        if not self.account_sid or not self.auth_token:
            raise ValueError("Twilio credentials (account_sid, auth_token) are required")
        
        # Configuración de números
        self.sms_from = self.config.get('sms_from') or os.getenv('TWILIO_SMS_FROM')
        self.whatsapp_from = self.config.get('whatsapp_from') or os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
        
        # Configuración adicional
        self.timeout = self.config.get('timeout', SMTP_TIMEOUT)
        self.webhook_url = self.config.get('webhook_url') or os.getenv('TWILIO_WEBHOOK_URL')
        
        # Inicializar cliente
        try:
            self.client = Client(self.account_sid, self.auth_token)
            logging.info("Twilio client initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Twilio client: {e}")
            raise
    
    
    async def send_sms(
        self,
        to: str,
        message: str,
        message_id: str = None,
        custom_params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Envía SMS via Twilio
        
        Args:
            to: Número destino (formato E.164: +1234567890)
            message: Contenido del SMS (max 1600 chars)
            message_id: ID interno para tracking
            custom_params: Parámetros adicionales
            
        Returns:
            Dict con resultado del envío
        """
        start_time = datetime.now()
        
        try:
            # Validaciones
            if not self.sms_from:
                raise ValueError("SMS from number not configured")
            
            self._validate_phone_number(to)
            self._validate_sms_content(message)
            
            # Preparar parámetros
            send_params = {
                'from_': self.sms_from,
                'to': to,
                'body': message
            }
            
            # Agregar webhook si está configurado
            if self.webhook_url:
                send_params['status_callback'] = self.webhook_url
            
            # Agregar parámetros personalizados
            if custom_params:
                if custom_params.get('media_url'):
                    send_params['media_url'] = custom_params['media_url']
                if custom_params.get('validity_period'):
                    send_params['validity_period'] = custom_params['validity_period']
            
            # Enviar SMS
            twilio_message = self.client.messages.create(**send_params)
            
            # Calcular tiempo de procesamiento
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                'success': True,
                'provider': 'twilio_sms',
                'provider_message_id': twilio_message.sid,
                'message_id': message_id,
                'status': twilio_message.status,
                'to': to,
                'processing_time_ms': int(processing_time),
                'details': {
                    'twilio_sid': twilio_message.sid,
                    'twilio_status': twilio_message.status,
                    'price': twilio_message.price,
                    'price_unit': twilio_message.price_unit,
                    'direction': twilio_message.direction,
                    'uri': twilio_message.uri
                }
            }
            
        except TwilioRestException as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                'success': False,
                'provider': 'twilio_sms',
                'message_id': message_id,
                'error_code': e.code,
                'error_message': e.msg,
                'processing_time_ms': int(processing_time),
                'details': {
                    'twilio_error_code': e.code,
                    'twilio_error_message': e.msg,
                    'more_info': e.uri
                }
            }
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                'success': False,
                'provider': 'twilio_sms',
                'message_id': message_id,
                'error_code': 'GENERAL_ERROR',
                'error_message': str(e),
                'processing_time_ms': int(processing_time)
            }
    
    
    async def send_whatsapp(
        self,
        to: str,
        message: str = None,
        template_name: str = None,
        template_params: List[str] = None,
        message_id: str = None,
        custom_params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Envía WhatsApp via Twilio Business API
        
        Args:
            to: Número destino con whatsapp: prefix
            message: Mensaje de texto libre (solo para usuarios que han iniciado conversación)
            template_name: Nombre del template aprobado
            template_params: Parámetros del template
            message_id: ID interno para tracking
            custom_params: Parámetros adicionales
            
        Returns:
            Dict con resultado del envío
        """
        start_time = datetime.now()
        
        try:
            # Validaciones
            if not self.whatsapp_from:
                raise ValueError("WhatsApp from number not configured")
            
            # Formatear número destino
            if not to.startswith('whatsapp:'):
                to = f'whatsapp:{to}'
            
            self._validate_phone_number(to.replace('whatsapp:', ''))
            
            # Preparar parámetros
            send_params = {
                'from_': self.whatsapp_from,
                'to': to
            }
            
            # Mensaje vs Template
            if template_name:
                # Usar template aprobado
                send_params['content_sid'] = template_name
                if template_params:
                    send_params['content_variables'] = json.dumps({
                        str(i+1): param for i, param in enumerate(template_params)
                    })
            elif message:
                # Mensaje de texto libre
                send_params['body'] = message
                self._validate_whatsapp_content(message)
            else:
                raise ValueError("Either message or template_name is required")
            
            # Agregar webhook si está configurado
            if self.webhook_url:
                send_params['status_callback'] = self.webhook_url
            
            # Agregar parámetros personalizados
            if custom_params:
                if custom_params.get('media_url'):
                    send_params['media_url'] = custom_params['media_url']
            
            # Enviar WhatsApp
            twilio_message = self.client.messages.create(**send_params)
            
            # Calcular tiempo de procesamiento
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                'success': True,
                'provider': 'twilio_whatsapp',
                'provider_message_id': twilio_message.sid,
                'message_id': message_id,
                'status': twilio_message.status,
                'to': to,
                'processing_time_ms': int(processing_time),
                'details': {
                    'twilio_sid': twilio_message.sid,
                    'twilio_status': twilio_message.status,
                    'price': twilio_message.price,
                    'price_unit': twilio_message.price_unit,
                    'direction': twilio_message.direction,
                    'uri': twilio_message.uri,
                    'used_template': template_name is not None
                }
            }
            
        except TwilioRestException as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                'success': False,
                'provider': 'twilio_whatsapp',
                'message_id': message_id,
                'error_code': e.code,
                'error_message': e.msg,
                'processing_time_ms': int(processing_time),
                'details': {
                    'twilio_error_code': e.code,
                    'twilio_error_message': e.msg,
                    'more_info': e.uri
                }
            }
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                'success': False,
                'provider': 'twilio_whatsapp',
                'message_id': message_id,
                'error_code': 'GENERAL_ERROR',
                'error_message': str(e),
                'processing_time_ms': int(processing_time)
            }
    
    
    def get_message_status(self, twilio_sid: str) -> Dict[str, Any]:
        """
        Consulta estado de mensaje por SID de Twilio
        """
        try:
            message = self.client.messages(twilio_sid).fetch()
            
            return {
                'success': True,
                'sid': message.sid,
                'status': message.status,
                'error_code': message.error_code,
                'error_message': message.error_message,
                'price': message.price,
                'price_unit': message.price_unit,
                'date_created': message.date_created.isoformat() if message.date_created else None,
                'date_sent': message.date_sent.isoformat() if message.date_sent else None,
                'date_updated': message.date_updated.isoformat() if message.date_updated else None
            }
            
        except TwilioRestException as e:
            return {
                'success': False,
                'error_code': e.code,
                'error_message': e.msg
            }
    
    
    def _validate_phone_number(self, phone: str) -> None:
        """
        Validación básica de número telefónico
        """
        # Remover prefijo whatsapp: si existe
        clean_phone = phone.replace('whatsapp:', '')
        
        if not clean_phone.startswith('+'):
            raise ValueError(f"Phone number must be in E.164 format (+1234567890): {clean_phone}")
        
        if len(clean_phone) < 8 or len(clean_phone) > 15:
            raise ValueError(f"Invalid phone number length: {clean_phone}")
    
    
    def _validate_sms_content(self, message: str) -> None:
        """
        Validación de contenido SMS
        """
        if not message or not message.strip():
            raise ValueError("SMS message cannot be empty")
        
        if len(message) > 1600:
            raise ValueError(f"SMS message too long: {len(message)} chars (max: 1600)")
    
    
    def _validate_whatsapp_content(self, message: str) -> None:
        """
        Validación de contenido WhatsApp
        """
        if not message or not message.strip():
            raise ValueError("WhatsApp message cannot be empty")
        
        if len(message) > 4096:
            raise ValueError(f"WhatsApp message too long: {len(message)} chars (max: 4096)")
    
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Prueba conexión con Twilio API
        """
        try:
            account = self.client.api.accounts(self.account_sid).fetch()
            
            return {
                'success': True,
                'account_sid': account.sid,
                'account_status': account.status,
                'account_name': account.friendly_name,
                'test_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'test_timestamp': datetime.now().isoformat()
            }


# Factory function para crear instancia
def create_twilio_service(provider_config: Dict[str, Any] = None) -> Optional[TwilioService]:
    """
    Factory para crear instancia de TwilioService con manejo de errores
    """
    try:
        return TwilioService(provider_config)
    except ImportError:
        logging.warning("Twilio service not available - missing dependencies")
        return None
    except Exception as e:
        logging.error(f"Failed to create Twilio service: {e}")
        return None