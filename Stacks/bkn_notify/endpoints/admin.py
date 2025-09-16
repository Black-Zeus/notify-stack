"""
Stacks\bkn_notify\endpoints\admin.py
Admin endpoints para gestión de providers, templates y configuración
"""

import logging
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime

from utils.config_loader import load_providers_config, load_config, load_policy_config
from utils.template_loader import get_available_templates 
from utils.redis_client import get_redis_client
from constants import HTTP_404_NOT_FOUND, HTTP_503_SERVICE_UNAVAILABLE

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/providers", response_model=Dict[str, Any])
async def list_providers():
    """
    Lista todos los providers configurados con su estado
    
    Returns:
        Dict con providers activos, inactivos y estadísticas
    """
    try:
        providers_config = load_providers_config()
        
        if not providers_config:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail="No providers configuration found"
            )
        
        active_providers = {}
        inactive_providers = {}
        providers_by_type = {"smtp": 0, "api": 0, "twilio": 0}
        providers_by_category = {}
        
        # Filtrar secciones de configuración que no son providers
        skip_sections = {
            'provider_groups', 'health_monitoring', 'cost_optimization',
            'regional_settings', 'development', 'statistics'
        }
        
        for name, config in providers_config.items():
            if name in skip_sections:
                continue
                
            if not isinstance(config, dict):
                continue
                
            # Clasificar por estado
            enabled = config.get('enabled', False)
            provider_type = config.get('type', 'unknown')
            category = config.get('category', 'uncategorized')
            
            provider_info = {
                "name": config.get('name', name),
                "type": provider_type,
                "provider_type": config.get('provider_type', ''),
                "category": category,
                "description": config.get('description', ''),
                "enabled": enabled,
                "priority": config.get('priority', 'medium'),
                "features": config.get('features', {}),
                "limits": {
                    "timeout": config.get('timeout'),
                    "max_recipients": config.get('max_recipients_per_message'),
                    "max_messages_per_hour": config.get('max_messages_per_hour')
                }
            }
            
            if enabled:
                active_providers[name] = provider_info
            else:
                inactive_providers[name] = provider_info
            
            # Estadísticas por tipo
            if provider_type in providers_by_type:
                providers_by_type[provider_type] += 1
            
            # Estadísticas por categoría
            providers_by_category[category] = providers_by_category.get(category, 0) + 1
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_providers": len(active_providers) + len(inactive_providers),
                "active_providers": len(active_providers),
                "inactive_providers": len(inactive_providers),
                "by_type": providers_by_type,
                "by_category": providers_by_category
            },
            "active_providers": active_providers,
            "inactive_providers": inactive_providers
        }
        
    except Exception as e:
        logging.error(f"Error listing providers: {e}")
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to load providers: {str(e)}"
        )


@router.get("/providers/{provider_name}", response_model=Dict[str, Any])
async def get_provider_details(provider_name: str):
    """
    Obtiene detalles específicos de un provider
    """
    try:
        providers_config = load_providers_config()
        
        if provider_name not in providers_config:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"Provider '{provider_name}' not found"
            )
        
        config = providers_config[provider_name]
        
        # Test de conectividad básico si es posible
        connection_status = "unknown"
        try:
            if config.get("type") == "twilio" and config.get("enabled"):
                from services.twilio_service import TwilioService
                service = TwilioService(provider_name)
                service_info = service.get_service_info()
                connection_status = service_info.get("status", "unknown")
        except Exception as test_error:
            logging.warning(f"Connection test failed for {provider_name}: {test_error}")
            connection_status = "test_failed"
        
        return {
            "status": "success",
            "provider_name": provider_name,
            "config": {
                "name": config.get('name', provider_name),
                "type": config.get('type'),
                "provider_type": config.get('provider_type', ''),
                "description": config.get('description', ''),
                "enabled": config.get('enabled', False),
                "priority": config.get('priority', 'medium'),
                "category": config.get('category', 'uncategorized'),
                "features": config.get('features', {}),
                "limits": {
                    "timeout": config.get('timeout'),
                    "max_recipients": config.get('max_recipients_per_message'),
                    "max_messages_per_hour": config.get('max_messages_per_hour'),
                    "max_message_length": config.get('max_message_length'),
                    "max_media_count": config.get('max_media_count')
                },
                "retry": config.get('retry', {}),
                "connection_status": connection_status
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting provider details for {provider_name}: {e}")
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get provider details: {str(e)}"
        )


@router.get("/config", response_model=Dict[str, Any])
async def get_system_config():
    """
    Obtiene configuración general del sistema (sin credenciales)
    """
    try:
        main_config = load_config()
        policy_config = load_policy_config()
        
        # Información sanitizada del sistema
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "system": {
                "app": main_config.get("app", {}),
                "logging": {
                    "level": main_config.get("logging", {}).get("level"),
                    "format": main_config.get("logging", {}).get("format")
                },
                "email": main_config.get("email", {}),
                "templates": main_config.get("templates", {})
            },
            "policies": {
                "whitelist": policy_config.get("whitelist", {}),
                "limits": policy_config.get("limits", {}),
                "routing": {
                    "default_provider": policy_config.get("routing", {}).get("default_provider"),
                    "rules_count": len(policy_config.get("routing", {}).get("rules", []))
                },
                "security": policy_config.get("security", {})
            }
        }
        
    except Exception as e:
        logging.error(f"Error getting system config: {e}")
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get system config: {str(e)}"
        )


@router.get("/health", response_model=Dict[str, Any])
async def admin_health_check(redis_client = Depends(get_redis_client)):
    """
    Health check completo del sistema para administradores
    """
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "components": {}
        }
        
        # Test Redis
        try:
            await redis_client.ping()
            health_status["components"]["redis"] = {"status": "healthy"}
        except Exception as e:
            health_status["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
            health_status["status"] = "degraded"
        
        # Test configuración
        try:
            providers = load_providers_config()
            active_count = sum(1 for p in providers.values() 
                             if isinstance(p, dict) and p.get('enabled', False))
            health_status["components"]["config"] = {
                "status": "healthy",
                "providers_loaded": len(providers),
                "active_providers": active_count
            }
        except Exception as e:
            health_status["components"]["config"] = {"status": "unhealthy", "error": str(e)}
            health_status["status"] = "degraded"
        
        # Test templates
        try:
            templates = get_available_templates ()
            health_status["components"]["templates"] = {
                "status": "healthy",
                "templates_available": len(templates)
            }
        except Exception as e:
            health_status["components"]["templates"] = {"status": "unhealthy", "error": str(e)}
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logging.error(f"Admin health check failed: {e}")
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )