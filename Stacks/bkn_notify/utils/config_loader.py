"""
Config loader utility
Carga y cache de archivos de configuración YAML
"""

import os
import yaml
import logging
import re
from typing import Dict, Any, Optional
from pathlib import Path

from constants import CONFIG_FILE, PROVIDERS_FILE, POLICY_FILE

# Cache global de configuraciones
_config_cache: Dict[str, Any] = {}


def expand_env_vars(content: str) -> str:
    """
    Expande variables de entorno en formato ${VAR_NAME}
    """
    def replace_var(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))  # Retorna original si no existe
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, content)


def load_yaml_file(file_path: str) -> Dict[str, Any]:
    """
    Carga archivo YAML con manejo de errores y expansión de variables de entorno
    """
    try:
        if not os.path.exists(file_path):
            logging.warning(f"Config file not found: {file_path}")
            return {}
        
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
            # Expandir variables de entorno ${VAR_NAME}
            content = expand_env_vars(content)
            
            data = yaml.safe_load(content) or {}
            logging.debug(f"Loaded config from {file_path}")
            return data
            
    except yaml.YAMLError as e:
        logging.error(f"YAML parsing error in {file_path}: {e}")
        raise ValueError(f"Invalid YAML format in {file_path}: {e}")
    except Exception as e:
        logging.error(f"Failed to load config {file_path}: {e}")
        raise


def load_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Carga configuración principal (config.yml)
    """
    cache_key = "main_config"
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    try:
        config = load_yaml_file(CONFIG_FILE)
        
        # Validaciones básicas
        if not config:
            logging.warning("Main config is empty, using defaults")
            config = get_default_config()
        
        # Cache resultado
        _config_cache[cache_key] = config
        logging.info("Main configuration loaded successfully")
        
        return config
        
    except Exception as e:
        logging.error(f"Failed to load main config: {e}")
        # Retornar configuración por defecto en caso de error
        default_config = get_default_config()
        _config_cache[cache_key] = default_config
        return default_config


def load_providers_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Carga configuración de proveedores (providers.yml)
    """
    cache_key = "providers_config"
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    try:
        providers = load_yaml_file(PROVIDERS_FILE)
        
        # Validar estructura de proveedores
        validated_providers = validate_providers_config(providers)
        
        # Cache resultado
        _config_cache[cache_key] = validated_providers
        logging.info(f"Providers configuration loaded: {len(validated_providers)} providers")
        
        return validated_providers
        
    except Exception as e:
        logging.error(f"Failed to load providers config: {e}")
        # Retornar configuración vacía en caso de error
        _config_cache[cache_key] = {}
        return {}


def load_policy_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Carga configuración de políticas (policy.yml)
    """
    cache_key = "policy_config"
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    try:
        policy = load_yaml_file(POLICY_FILE)
        
        # Validar estructura de políticas
        validated_policy = validate_policy_config(policy)
        
        # Cache resultado
        _config_cache[cache_key] = validated_policy
        logging.info("Policy configuration loaded successfully")
        
        return validated_policy
        
    except Exception as e:
        logging.error(f"Failed to load policy config: {e}")
        # Retornar políticas por defecto
        default_policy = get_default_policy()
        _config_cache[cache_key] = default_policy
        return default_policy


def validate_providers_config(providers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida configuración de proveedores
    """
    if not providers:
        logging.warning("No providers configured")
        return {}
    
    validated = {}
    
    # Secciones que no son proveedores individuales
    skip_sections = {
        'provider_groups', 'health_monitoring', 'cost_optimization',
        'regional_settings', 'development', 'statistics'
    }
    
    for name, config in providers.items():
        # Saltar secciones de configuración general
        if name in skip_sections:
            continue
            
        try:
            # Validaciones básicas
            if not isinstance(config, dict):
                logging.error(f"Provider {name}: invalid config format")
                continue
            
            provider_type = config.get("type")
            if provider_type not in ["smtp", "api"]:
                logging.error(f"Provider {name}: invalid type '{provider_type}'")
                continue
            
            # Validación específica por tipo
            if provider_type == "smtp":
                required_fields = ["host", "port", "username", "password"]
                if not all(field in config for field in required_fields):
                    logging.error(f"Provider {name}: missing required SMTP fields")
                    continue
            
            elif provider_type == "api":
                required_fields = ["endpoint", "api_key"]
                if not all(field in config for field in required_fields):
                    logging.error(f"Provider {name}: missing required API fields")
                    continue
            
            # Agregar configuración válida
            validated[name] = config
            logging.debug(f"Provider {name} validated successfully")
            
        except Exception as e:
            logging.error(f"Error validating provider {name}: {e}")
            continue
    
    return validated


def validate_policy_config(policy: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida configuración de políticas
    """
    if not policy:
        return get_default_policy()
    
    # Asegurar estructura mínima
    validated = {
        "whitelist": policy.get("whitelist", {}),
        "limits": policy.get("limits", {}),
        "routing": policy.get("routing", {}),
        "security": policy.get("security", {})
    }
    
    # Validar whitelist
    if "domains" not in validated["whitelist"]:
        validated["whitelist"]["domains"] = []
    
    # Validar límites
    limits = validated["limits"]
    if "max_recipients" not in limits:
        limits["max_recipients"] = 100
    if "max_attachments" not in limits:
        limits["max_attachments"] = 10
    if "max_attachment_size" not in limits:
        limits["max_attachment_size"] = 5242880  # 5MB
    
    return validated


def get_default_config() -> Dict[str, Any]:
    """
    Configuración por defecto del sistema
    """
    return {
        "app": {
            "name": "notify-api",
            "version": "1.0.0",
            "debug": False
        },
        "logging": {
            "level": "INFO",
            "format": "json"
        },
        "redis": {
            "url": "redis://bkn_redis:6379/0",
            "ttl_default": 3600
        },
        "celery": {
            "broker_url": "redis://bkn_redis:6379/0",
            "result_backend": "redis://bkn_redis:6379/0"
        }
    }


def get_default_policy() -> Dict[str, Any]:
    """
    Políticas por defecto del sistema
    """
    return {
        "whitelist": {
            "enabled": False,
            "domains": []
        },
        "limits": {
            "max_recipients": 100,
            "max_attachments": 10,
            "max_attachment_size": 5242880,
            "rate_limit_per_hour": 1000
        },
        "routing": {
            "default_provider": "smtp_default",
            "rules": []
        },
        "security": {
            "require_api_key": True,
            "allowed_origins": ["*"]
        }
    }


def get_provider_config(provider_name: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene configuración de un proveedor específico
    """
    providers = load_providers_config()
    return providers.get(provider_name)


def reload_all_configs():
    """
    Recarga todas las configuraciones (limpia cache)
    """
    global _config_cache
    _config_cache.clear()
    
    # Precargar configuraciones principales
    load_config(force_reload=True)
    load_providers_config(force_reload=True)
    load_policy_config(force_reload=True)
    
    logging.info("All configurations reloaded")


def get_config_info() -> Dict[str, Any]:
    """
    Obtiene información sobre configuraciones cargadas
    """
    return {
        "config_files": {
            "main": os.path.exists(CONFIG_FILE),
            "providers": os.path.exists(PROVIDERS_FILE),
            "policy": os.path.exists(POLICY_FILE)
        },
        "cached_configs": list(_config_cache.keys()),
        "providers_count": len(load_providers_config()),
        "last_loaded": "dynamic"  # TODO: agregar timestamps si es necesario
    }