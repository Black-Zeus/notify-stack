# =============================================================================
# Stacks/bkn_celery/providers/__init__.py
# =============================================================================
# Factory para crear instancias de providers según configuración

from typing import Dict, Any, Optional
import logging

from .base import BaseProvider, EmailMessage, SendResult
from .smtp import SMTPProvider
from .ses import SESProvider
from .sendgrid import SendGridProvider
from .mailgun import MailgunProvider

logger = logging.getLogger(__name__)


# Mapeo de tipos de provider a clases
PROVIDER_CLASSES = {
    'smtp': SMTPProvider,
    'api': {
        'ses': SESProvider,
        'sendgrid': SendGridProvider,
        'mailgun': MailgunProvider,
        'generic': None  # TODO: Implementar en siguiente fase
    }
}


def create_provider(provider_key: str, config: Dict[str, Any]) -> BaseProvider:
    """
    Factory para crear instancia de provider según configuración
    
    Args:
        provider_key: Identificador del provider (ej: 'smtp_primary', 'api_ses')
        config: Configuración del provider desde providers.yml
        
    Returns:
        Instancia de BaseProvider correspondiente
        
    Raises:
        ValueError: Si el tipo de provider no es soportado
    """
    provider_type = config.get('type', 'smtp')
    provider_subtype = config.get('provider_type')
    
    try:
        if provider_type == 'smtp':
            return SMTPProvider(config)
        
        elif provider_type == 'api':
            if not provider_subtype:
                raise ValueError(f"API provider '{provider_key}' missing 'provider_type'")
            
            api_providers = PROVIDER_CLASSES['api']
            provider_class = api_providers.get(provider_subtype)
            
            if not provider_class:
                raise ValueError(
                    f"Unsupported API provider type: {provider_subtype}. "
                    f"Supported: {list(api_providers.keys())}"
                )
            
            return provider_class(config)
        
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")
            
    except Exception as e:
        logger.error(f"Failed to create provider '{provider_key}': {e}")
        raise


def get_provider(provider_key: str, providers_config: Dict[str, Any]) -> BaseProvider:
    """
    Obtiene instancia de provider desde configuración
    
    Args:
        provider_key: Key del provider en providers.yml
        providers_config: Dict completo de providers desde config
        
    Returns:
        Instancia de BaseProvider
        
    Raises:
        ValueError: Si el provider no existe o está deshabilitado
    """
    if provider_key not in providers_config:
        raise ValueError(f"Provider '{provider_key}' not found in configuration")
    
    config = providers_config[provider_key]
    
    if not config.get('enabled', True):
        raise ValueError(f"Provider '{provider_key}' is disabled")
    
    return create_provider(provider_key, config)


def list_available_providers(providers_config: Dict[str, Any]) -> list[str]:
    """
    Lista los providers habilitados
    
    Args:
        providers_config: Dict de configuración de providers
        
    Returns:
        Lista de keys de providers habilitados
    """
    return [
        key for key, config in providers_config.items()
        if config.get('enabled', True)
    ]


def get_providers_by_type(
    providers_config: Dict[str, Any],
    provider_type: str
) -> Dict[str, BaseProvider]:
    """
    Obtiene todos los providers de un tipo específico
    
    Args:
        providers_config: Dict de configuración
        provider_type: 'smtp' o 'api'
        
    Returns:
        Dict de provider_key -> BaseProvider instance
    """
    result = {}
    
    for key, config in providers_config.items():
        if config.get('type') == provider_type and config.get('enabled', True):
            try:
                result[key] = create_provider(key, config)
            except Exception as e:
                logger.error(f"Failed to load provider '{key}': {e}")
    
    return result


def validate_all_providers(providers_config: Dict[str, Any]) -> Dict[str, bool]:
    """
    Valida configuración de todos los providers
    
    Args:
        providers_config: Dict de configuración
        
    Returns:
        Dict de provider_key -> validation_result (bool)
    """
    results = {}
    
    for key, config in providers_config.items():
        if not config.get('enabled', True):
            results[key] = None  # Skip disabled
            continue
        
        try:
            provider = create_provider(key, config)
            # Nota: validate_config es async, se debe llamar con await en contexto async
            results[key] = True
        except Exception as e:
            logger.error(f"Validation failed for '{key}': {e}")
            results[key] = False
    
    return results


# Exportar clases y funciones principales
__all__ = [
    'BaseProvider',
    'EmailMessage',
    'SendResult',
    'SMTPProvider',
    'SESProvider',
    'SendGridProvider',
    'MailgunProvider',
    'create_provider',
    'get_provider',
    'list_available_providers',
    'get_providers_by_type',
    'validate_all_providers',
]