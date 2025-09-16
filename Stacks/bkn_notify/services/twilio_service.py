# services/twilio_service.py
"""
Servicio base para Twilio - Cliente común para SMS y WhatsApp
Maneja autenticación, configuración y operaciones base de Twilio API
"""

import logging
from typing import Dict, Any, Optional, List
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

from utils.config_loader import get_provider_config
from constants import TWILIO_DEFAULT_TIMEOUT


class TwilioService:
    """
    Cliente base de Twilio para operaciones comunes
    """
    
    def __init__(self, provider_name: str):
        """
        Inicializa cliente Twilio con configuración del provider
        
        Args:
            provider_name: Nombre del provider (twilio_sms o twilio_whatsapp)
        """
        self.provider_name = provider_name
        self.config = self._load_config()
        self.client = self._create_client()
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Carga configuración específica del provider
        """
        config = get_provider_config(self.provider_name)
        if not config:
            raise ValueError(f"Provider config not found: {self.provider_name}")
            
        # Validar campos requeridos
        required_fields = ['account_sid', 'auth_token', 'from_number']
        for field in required_fields:
            if not config.get(field):
                raise ValueError(f"Missing required config field: {field}")
                
        return config
        
    def _create_client(self) -> Client:
        """
        Crea cliente Twilio autenticado
        """
        try:
            client = Client(
                self.config['account_sid'],
                self.config['auth_token']
            )
            
            # Test de conexión básico
            account = client.api.accounts(self.config['account_sid']).fetch()
            logging.info(f"Twilio client initialized - Account: {account.friendly_name}")
            
            return client
            
        except TwilioException as e:
            logging.error(f"Failed to initialize Twilio client: {e}")
            raise
            
    def validate_phone_number(self, phone_number: str) -> str:
        """
        Valida y normaliza número de teléfono
        
        Args:
            phone_number: Número a validar
            
        Returns:
            str: Número normalizado en formato E.164
        """
        if not phone_number:
            raise ValueError("Phone number is required")
            
        # Remover espacios y caracteres especiales
        clean_number = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Agregar + si no está presente
        if not clean_number.startswith("+"):
            # Asumir código de país Chile si no se especifica
            if not clean_number.startswith("56"):
                clean_number = "+56" + clean_number
            else:
                clean_number = "+" + clean_number
        
        # Validación básica de formato E.164
        if len(clean_number) < 10 or len(clean_number) > 15:
            raise ValueError(f"Invalid phone number format: {phone_number}")
            
        return clean_number
        
    def format_whatsapp_number(self, phone_number: str) -> str:
        """
        Formatea número para WhatsApp (whatsapp:+number)
        
        Args:
            phone_number: Número validado
            
        Returns:
            str: Número en formato WhatsApp
        """
        validated_number = self.validate_phone_number(phone_number)
        return f"whatsapp:{validated_number}"
        
    def get_from_number(self, channel: str = "sms") -> str:
        """
        Obtiene número origen según canal
        
        Args:
            channel: Canal de envío (sms o whatsapp)
            
        Returns:
            str: Número origen formateado
        """
        from_number = self.config['from_number']
        
        if channel.lower() == "whatsapp":
            return f"whatsapp:{from_number}"
        else:
            return from_number
            
    def validate_media_urls(self, media_list: List[Dict[str, Any]]) -> List[str]:
        """
        Valida y extrae URLs de media para WhatsApp
        
        Args:
            media_list: Lista de objetos media con url, type, caption
            
        Returns:
            List[str]: Lista de URLs válidas
        """
        if not media_list:
            return []
            
        validated_urls = []
        
        for media_item in media_list:
            if not isinstance(media_item, dict):
                logging.warning(f"Invalid media item format: {media_item}")
                continue
                
            url = media_item.get('url')
            if not url:
                logging.warning(f"Media item missing URL: {media_item}")
                continue
                
            # Validación básica de URL
            if not url.startswith(('http://', 'https://')):
                logging.warning(f"Invalid media URL format: {url}")
                continue
                
            validated_urls.append(url)
            
        return validated_urls
        
    def handle_twilio_error(self, error: TwilioException, message_id: str) -> Dict[str, Any]:
        """
        Maneja errores de Twilio y los convierte en formato estándar
        
        Args:
            error: Excepción de Twilio
            message_id: ID del mensaje para logging
            
        Returns:
            Dict: Resultado de error estandarizado
        """
        error_code = getattr(error, 'code', 'unknown')
        error_message = str(error)
        
        # Mapear códigos de error comunes
        if error_code == 21211:
            status = "invalid_phone"
            message = "Invalid phone number"
        elif error_code == 21408:
            status = "permission_denied"  
            message = "Permission to send WhatsApp message denied"
        elif error_code == 21610:
            status = "message_blocked"
            message = "Message blocked by carrier"
        else:
            status = "provider_error"
            message = f"Twilio error: {error_message}"
            
        logging.error(f"Twilio error for message {message_id}: {error_code} - {error_message}")
        
        return {
            "success": False,
            "status": status,
            "message": message,
            "provider_error_code": error_code,
            "provider_error_message": error_message,
            "timestamp": "2024-01-01T00:00:00Z"  # Será actualizado por el caller
        }
        
    def get_service_info(self) -> Dict[str, Any]:
        """
        Obtiene información del servicio para debugging
        """
        try:
            account = self.client.api.accounts(self.config['account_sid']).fetch()
            return {
                "provider": self.provider_name,
                "account_sid": self.config['account_sid'][:8] + "...",
                "account_name": account.friendly_name,
                "from_number": self.config['from_number'],
                "status": "connected"
            }
        except Exception as e:
            return {
                "provider": self.provider_name,
                "status": "error",
                "error": str(e)
            }