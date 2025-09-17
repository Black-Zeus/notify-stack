"""
Carga y validación de configuraciones - Updated with Variable Resolution
"""
import os
import logging
import yaml
from typing import Dict, Any, Optional

# Import del nuevo resolver
from utils.config_resolver import ConfigResolver, substitute_config_vars, debug_config_vars

# Rutas de archivos de configuración
CONFIG_DIR = "/app/Config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.yml")
PROVIDERS_FILE = os.path.join(CONFIG_DIR, "providers.yml")
POLICY_FILE = os.path.join(CONFIG_DIR, "policy.yml")
SECRETS_FILE = os.path.join(CONFIG_DIR, "secrets.env")

# Cache de configuraciones
_config_cache = {}

# Resolver global para variables
_resolver = ConfigResolver(warn_missing=True, strict_mode=False)


def load_yaml_file(filepath: str, resolve_vars: bool = True) -> Dict[str, Any]:
    """
    Carga archivo YAML de forma segura con resolución de variables
    
    Args:
        filepath: Path del archivo YAML
        resolve_vars: Si debe procesar plantillas ${VARIABLE}
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = yaml.safe_load(f) or {}
        
        # Procesar variables de entorno si está habilitado
        if resolve_vars and content:
            logging.debug(f"Resolving variables in: {filepath}")
            content = _resolver.substitute_env_vars(content)
            
            # Debug: mostrar variables procesadas en modo debug
            if os.getenv('DEBUG', '').lower() == 'true':
                debug_config_vars(content, os.path.basename(filepath))
        
        logging.debug(f"Loaded YAML file: {filepath}")
        return content
        
    except FileNotFoundError:
        logging.warning(f"Config file not found: {filepath}")
        return {}
    except yaml.YAMLError as e:
        logging.error(f"Invalid YAML in {filepath}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Error processing {filepath}: {e}")
        return {}


def load_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Carga configuración principal (config.yml) con variables resueltas
    """
    cache_key = "main_config"
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    try:
        # Cargar con resolución de variables
        config = load_yaml_file(CONFIG_FILE, resolve_vars=True)
        
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
    Carga configuración de proveedores (providers.yml) con variables resueltas
    """
    cache_key = "providers_config"
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    try:
        # CRÍTICO: Cargar con resolución de variables habilitada
        providers = load_yaml_file(PROVIDERS_FILE, resolve_vars=True)
        
        # Validar estructura de proveedores
        validated_providers = validate_providers_config(providers)
        
        # Mostrar variables faltantes si hay
        missing_vars = _resolver.get_missing_vars()
        if missing_vars:
            logging.warning(f"Missing environment variables: {sorted(missing_vars)}")
        
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
    Carga configuración de políticas (policy.yml) con variables resueltas
    """
    cache_key = "policy_config"
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    try:
        # Cargar con resolución de variables
        policy = load_yaml_file(POLICY_FILE, resolve_vars=True)
        
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
    Valida configuración de proveedores y filtra los deshabilitados
    ACTUALIZADO: Valida que las variables se resolvieron correctamente
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
            
            # VALIDACIÓN CRÍTICA: Verificar enabled flag
            if not config.get("enabled", True):
                logging.info(f"Provider {name}: disabled, skipping")
                continue
            
            provider_type = config.get("type")
            if provider_type not in ["smtp", "api", "twilio"]:
                logging.error(f"Provider {name}: invalid type '{provider_type}'")
                continue
            
            # NUEVA VALIDACIÓN: Verificar que variables críticas se resolvieron
            if provider_type in ["twilio", "api"]:
                # Verificar que no quedan plantillas sin resolver
                if _has_unresolved_templates(config):
                    logging.error(f"Provider {name}: unresolved template variables")
                    continue
            
            # Validación específica por tipo
            if provider_type == "smtp":
                required_fields = ["host", "port"]
                if not all(field in config for field in required_fields):
                    logging.error(f"Provider {name}: missing required SMTP fields")
                    continue
            
            elif provider_type == "api":
                # Verificar si es un proveedor Twilio
                twilio_provider_type = config.get("provider_type", "")
                
                if twilio_provider_type in ["twilio_sms", "twilio_whatsapp"]:
                    # Validación específica para Twilio
                    required_fields = ["account_sid", "auth_token", "from_number"]
                    if not all(field in config for field in required_fields):
                        logging.error(f"Provider {name}: missing required Twilio fields")
                        continue
                    
                    # NUEVA: Validar que las credenciales no estén vacías
                    account_sid = config.get("account_sid", "")
                    auth_token = config.get("auth_token", "")
                    
                    if not account_sid or not auth_token:
                        logging.error(f"Provider {name}: empty Twilio credentials")
                        continue
                    
                    if account_sid.startswith("${") or auth_token.startswith("${"):
                        logging.error(f"Provider {name}: unresolved Twilio credential templates")
                        continue
                        
                    logging.debug(f"Provider {name}: Twilio provider validated successfully")
                else:
                    # Validación para API genéricas (SendGrid, SES, etc.)
                    required_fields = ["endpoint"]
                    if not all(field in config for field in required_fields):
                        logging.error(f"Provider {name}: missing required API fields")
                        continue
            
            elif provider_type == "twilio":
                # Mantener para compatibilidad con configuraciones que usen type: "twilio"
                required_fields = ["account_sid", "auth_token", "from_number"]
                if not all(field in config for field in required_fields):
                    logging.error(f"Provider {name}: missing required Twilio fields")
                    continue
                    
                # Validar provider_type específico de Twilio
                twilio_provider_type = config.get("provider_type")
                if twilio_provider_type not in ["sms", "whatsapp", "twilio_sms", "twilio_whatsapp"]:
                    logging.error(f"Provider {name}: invalid Twilio provider_type '{twilio_provider_type}'")
                    continue
            
            # Agregar configuración válida Y HABILITADA
            validated[name] = config
            logging.debug(f"Provider {name} validated and enabled successfully")
            
        except Exception as e:
            logging.error(f"Error validating provider {name}: {e}")
            continue
    
    return validated


def _has_unresolved_templates(obj: Any) -> bool:
    """
    Verifica si quedan plantillas ${VARIABLE} sin resolver
    """
    import re
    pattern = re.compile(r'\$\{[^}]+\}')
    
    if isinstance(obj, dict):
        return any(_has_unresolved_templates(value) for value in obj.values())
    elif isinstance(obj, list):
        return any(_has_unresolved_templates(item) for item in obj)
    elif isinstance(obj, str):
        return bool(pattern.search(obj))
    else:
        return False


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
    Obtiene configuración de un proveedor específico (solo si está habilitado)
    Las variables ya están resueltas
    """
    providers = load_providers_config()
    config = providers.get(provider_name)
    
    if config and os.getenv('DEBUG', '').lower() == 'true':
        logging.debug(f"Provider {provider_name} config: account_sid={config.get('account_sid', 'N/A')[:10]}...")
    
    return config


def get_enabled_providers() -> Dict[str, Any]:
    """
    Obtiene solo los proveedores habilitados con variables resueltas
    """
    return load_providers_config()  # Ya filtrado por enabled=true


def reload_all_configs():
    """
    Recarga todas las configuraciones (limpia cache)
    """
    global _config_cache
    _config_cache.clear()
    
    # Limpiar variables faltantes del resolver
    _resolver.clear_missing_vars()
    
    # Precargar configuraciones principales
    load_config(force_reload=True)
    load_providers_config(force_reload=True)
    load_policy_config(force_reload=True)
    
    logging.info("All configurations reloaded")


def get_config_info() -> Dict[str, Any]:
    """
    Obtiene información sobre configuraciones cargadas
    ACTUALIZADO: Incluye info sobre variables resueltas
    """
    return {
        "config_files": {
            "main": os.path.exists(CONFIG_FILE),
            "providers": os.path.exists(PROVIDERS_FILE),
            "policy": os.path.exists(POLICY_FILE)
        },
        "cached_configs": list(_config_cache.keys()),
        "providers_count": len(load_providers_config()),
        "missing_variables": sorted(_resolver.get_missing_vars()),
        "variable_resolution": "enabled",
        "last_loaded": "dynamic"
    }


def validate_critical_vars() -> Dict[str, Any]:
    """
    NUEVA: Valida variables críticas para proveedores activos
    """
    results = {
        "valid": True,
        "missing_vars": [],
        "provider_status": {}
    }
    
    providers = load_providers_config()
    
    for name, config in providers.items():
        provider_type = config.get("type")
        provider_subtype = config.get("provider_type", "")
        
        # Validar variables críticas por tipo de proveedor
        missing = []
        
        if provider_type == "twilio" or provider_subtype in ["twilio_sms", "twilio_whatsapp"]:
            if not config.get("account_sid"):
                missing.append("TWILIO_ACCOUNT_SID")
            if not config.get("auth_token"):
                missing.append("TWILIO_AUTH_TOKEN")
        
        results["provider_status"][name] = {
            "valid": len(missing) == 0,
            "missing_vars": missing
        }
        
        if missing:
            results["valid"] = False
            results["missing_vars"].extend(missing)
    
    # Remover duplicados
    results["missing_vars"] = sorted(set(results["missing_vars"]))
    
    return results