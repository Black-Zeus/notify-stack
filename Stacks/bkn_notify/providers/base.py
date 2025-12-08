# =============================================================================
# Stacks/bkn_celery/providers/base.py
# =============================================================================
# Interface base para proveedores de email (SMTP y API)
# Define el contrato común que todos los providers deben cumplir

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Mensaje de email normalizado para todos los providers"""
    to: List[str]
    subject: str
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    custom_headers: Optional[Dict[str, str]] = None
    message_id: Optional[str] = None


@dataclass
class SendResult:
    """Resultado de envío normalizado"""
    success: bool
    message_id: Optional[str] = None
    provider: Optional[str] = None
    error: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class BaseProvider(ABC):
    """Clase base abstracta para todos los proveedores de email"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa el provider con su configuración
        
        Args:
            config: Dict con la configuración del provider desde providers.yml
        """
        self.config = config
        self.provider_name = config.get('name', 'unknown')
        self.provider_type = config.get('type', 'unknown')
        self.enabled = config.get('enabled', True)
        self.timeout = config.get('timeout', 30)
        
        # Retry configuration
        retry_config = config.get('retry', {})
        self.max_retries = retry_config.get('max_attempts', 3)
        self.retry_backoff = retry_config.get('backoff_factor', 2)
        self.initial_delay = retry_config.get('initial_delay', 60)
        
        # Limits
        self.max_recipients = config.get('max_recipients_per_message', 100)
        self.max_attachment_size = config.get('max_attachment_size', 5242880)
        
        # Features
        self.features = config.get('features', {})
        
        logger.info(f"Initialized {self.provider_name} provider (type: {self.provider_type})")
    
    @abstractmethod
    async def send(self, message: EmailMessage) -> SendResult:
        """
        Envía un mensaje de email
        
        Args:
            message: EmailMessage objeto con los datos del email
            
        Returns:
            SendResult con el resultado del envío
        """
        pass
    
    @abstractmethod
    async def validate_config(self) -> bool:
        """
        Valida que la configuración del provider es correcta
        
        Returns:
            True si la configuración es válida
        """
        pass
    
    async def test_connection(self) -> bool:
        """
        Prueba la conexión al provider (opcional)
        
        Returns:
            True si la conexión es exitosa
        """
        try:
            return await self.validate_config()
        except Exception as e:
            logger.error(f"Connection test failed for {self.provider_name}: {e}")
            return False
    
    def validate_message(self, message: EmailMessage) -> bool:
        """
        Valida que el mensaje cumple con los límites del provider
        
        Args:
            message: EmailMessage a validar
            
        Returns:
            True si el mensaje es válido
            
        Raises:
            ValueError: Si el mensaje no cumple los límites
        """
        # Validar destinatarios
        total_recipients = len(message.to)
        if message.cc:
            total_recipients += len(message.cc)
        if message.bcc:
            total_recipients += len(message.bcc)
            
        if total_recipients > self.max_recipients:
            raise ValueError(
                f"Too many recipients: {total_recipients} (max: {self.max_recipients})"
            )
        
        # Validar attachments si existen
        if message.attachments and not self.features.get('attachments', False):
            raise ValueError(f"Provider {self.provider_name} does not support attachments")
        
        if message.attachments:
            for attachment in message.attachments:
                size = attachment.get('size', 0)
                if size > self.max_attachment_size:
                    raise ValueError(
                        f"Attachment too large: {size} bytes (max: {self.max_attachment_size})"
                    )
        
        # Validar HTML si existe
        if message.body_html and not self.features.get('html_support', True):
            raise ValueError(f"Provider {self.provider_name} does not support HTML emails")
        
        return True
    
    def get_from_address(self, message: EmailMessage) -> tuple[str, str]:
        """
        Obtiene el from email y name, con fallback a config
        
        Args:
            message: EmailMessage con posible from_email/from_name
            
        Returns:
            Tuple (from_email, from_name)
        """
        from_email = message.from_email or self.config.get('from_email', 'noreply@notify.local')
        from_name = message.from_name or self.config.get('from_name', 'Notify System')
        
        return from_email, from_name
    
    def supports_feature(self, feature: str) -> bool:
        """
        Verifica si el provider soporta una característica
        
        Args:
            feature: Nombre de la característica (html_support, attachments, etc)
            
        Returns:
            True si soporta la característica
        """
        return self.features.get(feature, False)
    
    def get_retry_delay(self, attempt: int) -> int:
        """
        Calcula el delay para el siguiente retry con backoff exponencial
        
        Args:
            attempt: Número de intento actual (1-based)
            
        Returns:
            Delay en segundos
        """
        return self.initial_delay * (self.retry_backoff ** (attempt - 1))
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.provider_name} type={self.provider_type}>"


class ProviderError(Exception):
    """Excepción base para errores de providers"""
    
    def __init__(self, message: str, provider: str = None, retry_after: int = None):
        super().__init__(message)
        self.provider = provider
        self.retry_after = retry_after


class ProviderConnectionError(ProviderError):
    """Error de conexión al provider"""
    pass


class ProviderAuthError(ProviderError):
    """Error de autenticación con el provider"""
    pass


class ProviderRateLimitError(ProviderError):
    """Provider ha excedido rate limit"""
    pass


class ProviderValidationError(ProviderError):
    """Error de validación de datos"""
    pass