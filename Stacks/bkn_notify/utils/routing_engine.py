"""
Routing engine utility
Selecciona proveedor SMTP/API basado en reglas configuradas
"""

import re
import logging
from typing import Dict, Any, Optional, List

from .config_loader import load_policy_config, load_providers_config


async def apply_routing(request) -> Dict[str, Any]:
    """
    Aplica reglas de routing para seleccionar proveedor
    
    Prioridad:
    1. Provider específico en request.provider (si es válido y habilitado)
    2. Routing hint en request.routing_hint
    3. Reglas configuradas en policy.yml
    4. Provider por defecto
    
    Returns:
        Dict con provider, routing_reason, config
    """
    
    policy = load_policy_config()
    providers = load_providers_config()  # Ya filtrado por enabled=true
    
    if not providers:
        raise ValueError("No email providers configured or enabled")
    
    routing_config = policy.get("routing", {})
    default_provider = routing_config.get("default_provider")
    
    # Verificar que hay un provider por defecto válido y habilitado
    if not default_provider or default_provider not in providers:
        # Usar el primer provider disponible como fallback
        default_provider = next(iter(providers.keys()))
        logging.warning(f"Default provider not configured or disabled, using: {default_provider}")
    
    selected_provider = None
    routing_reason = "default"
    
    try:
        # 1. Provider específico solicitado
        if request.provider:
            if request.provider in providers:
                # ✅ Provider existe Y está habilitado (config_loader ya filtró)
                selected_provider = request.provider
                routing_reason = "explicit_request"
                logging.debug(f"Using explicit provider: {request.provider}")
            else:
                logging.warning(f"Requested provider '{request.provider}' not found or disabled, applying routing rules")
        
        # 2. Routing hint
        if not selected_provider and request.routing_hint:
            hint_provider = await apply_routing_hint(request.routing_hint, providers, routing_config)
            if hint_provider:
                selected_provider = hint_provider
                routing_reason = f"routing_hint:{request.routing_hint}"
                logging.debug(f"Provider selected by hint '{request.routing_hint}': {hint_provider}")
        
        # 3. Reglas de routing configuradas
        if not selected_provider:
            rule_provider = await apply_routing_rules(request, providers, routing_config)
            if rule_provider:
                selected_provider = rule_provider["provider"]
                routing_reason = f"rule:{rule_provider['rule_name']}"
                logging.debug(f"Provider selected by rule '{rule_provider['rule_name']}': {selected_provider}")
        
        # 4. Provider por defecto
        if not selected_provider:
            selected_provider = default_provider
            routing_reason = "default"
        
        # Verificar que el provider seleccionado está disponible y habilitado
        provider_config = providers.get(selected_provider)
        if not provider_config:
            logging.error(f"Selected provider '{selected_provider}' not found or disabled")
            # Fallback al primer provider disponible
            selected_provider = next(iter(providers.keys()))
            provider_config = providers[selected_provider]
            routing_reason = "fallback"
        
        # ✅ Validación adicional: verificar enabled en el config específico
        if not provider_config.get("enabled", True):
            logging.warning(f"Provider '{selected_provider}' is disabled, searching for alternative")
            # Buscar primer proveedor habilitado
            for alt_name, alt_config in providers.items():
                if alt_config.get("enabled", True):
                    selected_provider = alt_name
                    provider_config = alt_config
                    routing_reason = "enabled_fallback"
                    break
        
        result = {
            "provider": selected_provider,
            "routing_reason": routing_reason,
            "provider_config": provider_config,
            "provider_type": provider_config.get("type", "smtp"),
            "provider_enabled": provider_config.get("enabled", True)
        }
        
        logging.info(f"Routing decision: {selected_provider} (reason: {routing_reason})")
        return result
        
    except Exception as e:
        logging.error(f"Routing engine error: {e}")
        # Fallback seguro: buscar cualquier proveedor habilitado
        for fallback_name, fallback_config in providers.items():
            if fallback_config.get("enabled", True):
                return {
                    "provider": fallback_name,
                    "routing_reason": "error_fallback",
                    "provider_config": fallback_config,
                    "provider_type": fallback_config.get("type", "smtp"),
                    "provider_enabled": True
                }
        
        # Si no hay proveedores habilitados, error crítico
        raise ValueError("No enabled providers available for routing")


async def apply_routing_hint(hint: str, providers: Dict[str, Any], routing_config: Dict[str, Any]) -> Optional[str]:
    """
    Aplica routing hint para selección de proveedor
    
    Hints soportados:
    - "high_priority" -> proveedor para emails importantes
    - "bulk" -> proveedor para envíos masivos
    - "transactional" -> proveedor para emails transaccionales
    - "marketing" -> proveedor para marketing
    """
    
    hint_mapping = routing_config.get("hint_mapping", {})
    
    if hint in hint_mapping:
        suggested_provider = hint_mapping[hint]
        if suggested_provider in providers:
            return suggested_provider
        else:
            logging.warning(f"Hint mapped provider '{suggested_provider}' not found or disabled")
    
    # Hints predefinidos si no hay mapping
    default_hints = {
        "high_priority": _find_provider_by_priority(providers, "high"),
        "bulk": _find_provider_by_type(providers, "bulk"),
        "transactional": _find_provider_by_type(providers, "transactional"),
        "marketing": _find_provider_by_type(providers, "marketing")
    }
    
    return default_hints.get(hint)


async def apply_routing_rules(request, providers: Dict[str, Any], routing_config: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Aplica reglas de routing configuradas
    
    Formato de reglas en policy.yml:
    routing:
      rules:
        - name: "bulk_emails"
          condition:
            recipient_count: ">= 10"
          provider: "smtp_bulk"
        - name: "admin_domain"
          condition:
            recipient_domain: "admin.company.com"
          provider: "smtp_secure"
    """
    
    rules = routing_config.get("rules", [])
    
    for rule in rules:
        if await _evaluate_rule_condition(request, rule.get("condition", {})):
            provider = rule.get("provider")
            if provider and provider in providers:
                return {
                    "provider": provider,
                    "rule_name": rule.get("name", "unnamed")
                }
            else:
                logging.warning(f"Rule '{rule.get('name')}' specifies invalid or disabled provider: {provider}")
    
    return None


async def _evaluate_rule_condition(request, condition: Dict[str, Any]) -> bool:
    """
    Evalúa condición de regla de routing
    """
    try:
        # Condición por cantidad de destinatarios
        if "recipient_count" in condition:
            total_recipients = len(request.to) + len(request.cc or []) + len(request.bcc or [])
            if not _evaluate_numeric_condition(total_recipients, condition["recipient_count"]):
                return False
        
        # Condición por dominio de destinatario
        if "recipient_domain" in condition:
            target_domain = condition["recipient_domain"]
            all_recipients = request.to + (request.cc or []) + (request.bcc or [])
            
            domain_match = False
            for email in all_recipients:
                domain = email.split('@')[-1].lower() if '@' in email else ''
                if domain == target_domain.lower():
                    domain_match = True
                    break
            
            if not domain_match:
                return False
        
        # Condición por patrón de destinatario
        if "recipient_pattern" in condition:
            pattern = condition["recipient_pattern"]
            all_recipients = request.to + (request.cc or []) + (request.bcc or [])
            
            pattern_match = False
            for email in all_recipients:
                if re.match(pattern, email, re.IGNORECASE):
                    pattern_match = True
                    break
            
            if not pattern_match:
                return False
        
        # Condición por template
        if "template_id" in condition:
            if request.template_id != condition["template_id"]:
                return False
        
        # Condición por patrón de template
        if "template_pattern" in condition:
            if not request.template_id or not re.match(condition["template_pattern"], request.template_id):
                return False
        
        # Condición por hora del día (ejemplo: "08:00-18:00")
        if "time_range" in condition:
            from datetime import datetime
            current_hour = datetime.now().hour
            time_range = condition["time_range"]
            
            if "-" in time_range:
                start_hour, end_hour = time_range.split("-")
                start_hour = int(start_hour.split(":")[0])
                end_hour = int(end_hour.split(":")[0])
                
                if not (start_hour <= current_hour <= end_hour):
                    return False
        
        return True
        
    except Exception as e:
        logging.error(f"Error evaluating routing condition: {e}")
        return False


def _evaluate_numeric_condition(value: int, condition: str) -> bool:
    """
    Evalúa condición numérica (ej: ">= 10", "< 5", "== 1")
    """
    try:
        condition = condition.strip()
        
        if condition.startswith(">="):
            return value >= int(condition[2:].strip())
        elif condition.startswith("<="):
            return value <= int(condition[2:].strip())
        elif condition.startswith(">"):
            return value > int(condition[1:].strip())
        elif condition.startswith("<"):
            return value < int(condition[1:].strip())
        elif condition.startswith("=="):
            return value == int(condition[2:].strip())
        elif condition.startswith("!="):
            return value != int(condition[2:].strip())
        else:
            # Asume igualdad si no hay operador
            return value == int(condition)
            
    except (ValueError, IndexError):
        logging.error(f"Invalid numeric condition: {condition}")
        return False


def _find_provider_by_priority(providers: Dict[str, Any], priority: str) -> Optional[str]:
    """
    Encuentra proveedor por prioridad configurada (solo habilitados)
    """
    for name, config in providers.items():
        if config.get("priority") == priority and config.get("enabled", True):
            return name
    return None


def _find_provider_by_type(providers: Dict[str, Any], provider_type: str) -> Optional[str]:
    """
    Encuentra proveedor por tipo/categoría (solo habilitados)
    """
    for name, config in providers.items():
        if config.get("category") == provider_type and config.get("enabled", True):
            return name
    return None


def get_routing_summary() -> Dict[str, Any]:
    """
    Retorna resumen de configuración de routing
    """
    try:
        policy = load_policy_config()
        providers = load_providers_config()  # Solo habilitados
        routing_config = policy.get("routing", {})
        
        return {
            "providers_available": list(providers.keys()),
            "providers_enabled_count": len(providers),
            "default_provider": routing_config.get("default_provider"),
            "default_provider_enabled": routing_config.get("default_provider") in providers,
            "rules_count": len(routing_config.get("rules", [])),
            "hint_mappings": routing_config.get("hint_mapping", {}),
            "providers_by_type": {
                name: config.get("type", "smtp") 
                for name, config in providers.items()
            },
            "providers_status": {
                name: {
                    "type": config.get("type", "smtp"),
                    "enabled": config.get("enabled", True),
                    "priority": config.get("priority"),
                    "category": config.get("category")
                }
                for name, config in providers.items()
            }
        }
    except Exception as e:
        logging.error(f"Error getting routing summary: {e}")
        return {"error": str(e)}