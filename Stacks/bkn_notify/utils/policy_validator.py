"""
Policy validator utility
Valida requests contra políticas de seguridad y límites
"""

import re
import logging
from typing import List, Dict, Any
from email_validator import validate_email, EmailNotValidError

from .config_loader import load_policy_config
from app.constants import MAX_RECIPIENTS, MAX_ATTACHMENTS, MAX_ATTACHMENT_SIZE


async def validate_request(request) -> None:
    """
    Valida request contra todas las políticas configuradas
    Raises ValueError si alguna política es violada
    """
    
    # Cargar políticas
    policy = load_policy_config()
    
    # Validaciones básicas
    await validate_recipients(request.to, request.cc, request.bcc, policy)
    await validate_content_limits(request, policy)
    await validate_whitelist(request.to, request.cc, request.bcc, policy)
    await validate_attachments(request.attachments, policy)
    
    logging.debug(f"Request validation passed for {len(request.to)} recipients")


async def validate_recipients(to: List[str], cc: List[str] = None, bcc: List[str] = None, policy: Dict[str, Any] = None) -> None:
    """
    Valida destinatarios: formato email y límites de cantidad
    """
    if not policy:
        policy = load_policy_config()
    
    # Combinar todos los destinatarios
    all_recipients = []
    if to:
        all_recipients.extend(to)
    if cc:
        all_recipients.extend(cc)
    if bcc:
        all_recipients.extend(bcc)
    
    # Verificar que hay al menos un destinatario
    if not all_recipients:
        raise ValueError("At least one recipient (to, cc, or bcc) is required")
    
    # Verificar límite de destinatarios
    max_recipients = policy.get("limits", {}).get("max_recipients", MAX_RECIPIENTS)
    if len(all_recipients) > max_recipients:
        raise ValueError(f"Too many recipients: {len(all_recipients)} (max: {max_recipients})")
    
    # Validar formato de cada email
    unique_recipients = set()
    for email in all_recipients:
        if not email or not email.strip():
            raise ValueError("Empty email address found")
        
        email = email.strip().lower()
        
        # Verificar duplicados
        if email in unique_recipients:
            logging.warning(f"Duplicate recipient found: {email}")
        unique_recipients.add(email)
        
        # Validar formato de email
        try:
            validate_email(email)
        except EmailNotValidError as e:
            raise ValueError(f"Invalid email address '{email}': {str(e)}")
    
    logging.debug(f"Recipients validation passed: {len(unique_recipients)} unique emails")


async def validate_whitelist(to: List[str], cc: List[str] = None, bcc: List[str] = None, policy: Dict[str, Any] = None) -> None:
    """
    Valida destinatarios contra whitelist de dominios si está habilitada
    """
    if not policy:
        policy = load_policy_config()
    
    whitelist_config = policy.get("whitelist", {})
    if not whitelist_config.get("enabled", False):
        return  # Whitelist deshabilitada
    
    allowed_domains = whitelist_config.get("domains", [])
    if not allowed_domains:
        logging.warning("Whitelist enabled but no domains configured")
        return
    
    # Normalizar dominios permitidos
    allowed_domains = [domain.lower().strip() for domain in allowed_domains]
    
    # Combinar todos los destinatarios
    all_recipients = []
    if to:
        all_recipients.extend(to)
    if cc:
        all_recipients.extend(cc)
    if bcc:
        all_recipients.extend(bcc)
    
    # Verificar cada destinatario
    for email in all_recipients:
        email = email.strip().lower()
        domain = email.split('@')[-1] if '@' in email else ''
        
        if domain not in allowed_domains:
            raise ValueError(f"Domain '{domain}' not in whitelist. Allowed domains: {allowed_domains}")
    
    logging.debug(f"Whitelist validation passed for {len(all_recipients)} recipients")


async def validate_content_limits(request, policy: Dict[str, Any] = None) -> None:
    """
    Valida límites de contenido (subject, body, etc.)
    """
    if not policy:
        policy = load_policy_config()
    
    limits = policy.get("limits", {})
    
    # Validar subject
    if request.subject:
        max_subject_length = limits.get("max_subject_length", 998)  # RFC 2822 limit
        if len(request.subject) > max_subject_length:
            raise ValueError(f"Subject too long: {len(request.subject)} chars (max: {max_subject_length})")
    
    # Validar body_text
    if request.body_text:
        max_body_length = limits.get("max_body_length", 1048576)  # 1MB
        if len(request.body_text) > max_body_length:
            raise ValueError(f"Text body too long: {len(request.body_text)} chars (max: {max_body_length})")
    
    # Validar body_html
    if request.body_html:
        max_body_length = limits.get("max_body_length", 1048576)  # 1MB
        if len(request.body_html) > max_body_length:
            raise ValueError(f"HTML body too long: {len(request.body_html)} chars (max: {max_body_length})")
    
    # Validar que hay contenido
    if not request.template_id and not request.body_text and not request.body_html:
        raise ValueError("Either template_id or body content (text/html) is required")
    
    logging.debug("Content limits validation passed")


async def validate_attachments(attachments: List[Dict] = None, policy: Dict[str, Any] = None) -> None:
    """
    Valida attachments: cantidad y tamaño
    """
    if not attachments:
        return  # Sin attachments
    
    if not policy:
        policy = load_policy_config()
    
    limits = policy.get("limits", {})
    
    # Verificar cantidad de attachments
    max_attachments = limits.get("max_attachments", MAX_ATTACHMENTS)
    if len(attachments) > max_attachments:
        raise ValueError(f"Too many attachments: {len(attachments)} (max: {max_attachments})")
    
    # Verificar cada attachment
    max_attachment_size = limits.get("max_attachment_size", MAX_ATTACHMENT_SIZE)
    total_size = 0
    
    for i, attachment in enumerate(attachments):
        if not isinstance(attachment, dict):
            raise ValueError(f"Attachment {i}: invalid format, must be object")
        
        # Verificar campos requeridos
        if "filename" not in attachment:
            raise ValueError(f"Attachment {i}: filename is required")
        
        if "content" not in attachment:
            raise ValueError(f"Attachment {i}: content is required")
        
        # Verificar nombre de archivo
        filename = attachment["filename"]
        if not filename or not filename.strip():
            raise ValueError(f"Attachment {i}: filename cannot be empty")
        
        # Verificar caracteres peligrosos en filename
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
        if any(char in filename for char in dangerous_chars):
            raise ValueError(f"Attachment {i}: filename contains dangerous characters")
        
        # Verificar tamaño (asumiendo base64)
        content_size = len(attachment["content"])
        if content_size > max_attachment_size:
            raise ValueError(f"Attachment {i} too large: {content_size} bytes (max: {max_attachment_size})")
        
        total_size += content_size
    
    # Verificar tamaño total
    max_total_size = limits.get("max_total_attachments_size", max_attachment_size * max_attachments)
    if total_size > max_total_size:
        raise ValueError(f"Total attachments size too large: {total_size} bytes (max: {max_total_size})")
    
    logging.debug(f"Attachments validation passed: {len(attachments)} files, {total_size} bytes")


async def validate_template_access(template_id: str, policy: Dict[str, Any] = None) -> None:
    """
    Valida acceso a templates (si hay restricciones configuradas)
    """
    if not template_id:
        return
    
    if not policy:
        policy = load_policy_config()
    
    template_policy = policy.get("templates", {})
    
    # Verificar si hay restricciones de templates
    allowed_templates = template_policy.get("allowed_templates", [])
    if allowed_templates and template_id not in allowed_templates:
        raise ValueError(f"Template '{template_id}' not in allowed list: {allowed_templates}")
    
    # Verificar patrones bloqueados
    blocked_patterns = template_policy.get("blocked_patterns", [])
    for pattern in blocked_patterns:
        if re.match(pattern, template_id):
            raise ValueError(f"Template '{template_id}' matches blocked pattern: {pattern}")
    
    logging.debug(f"Template access validation passed: {template_id}")


async def validate_rate_limit(sender_info: Dict[str, Any], policy: Dict[str, Any] = None) -> None:
    """
    Valida rate limiting (implementación básica)
    TODO: Integrar con Redis para rate limiting real
    """
    if not policy:
        policy = load_policy_config()
    
    rate_limit_config = policy.get("rate_limit", {})
    if not rate_limit_config.get("enabled", False):
        return
    
    # Placeholder para implementación futura
    # Aquí se integraría con Redis para tracking de rates
    logging.debug("Rate limit validation (placeholder)")


def get_validation_summary(policy: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Retorna resumen de políticas configuradas
    """
    if not policy:
        policy = load_policy_config()
    
    return {
        "whitelist": {
            "enabled": policy.get("whitelist", {}).get("enabled", False),
            "domains_count": len(policy.get("whitelist", {}).get("domains", []))
        },
        "limits": {
            "max_recipients": policy.get("limits", {}).get("max_recipients", MAX_RECIPIENTS),
            "max_attachments": policy.get("limits", {}).get("max_attachments", MAX_ATTACHMENTS),
            "max_attachment_size": policy.get("limits", {}).get("max_attachment_size", MAX_ATTACHMENT_SIZE)
        },
        "templates": {
            "restrictions_enabled": bool(policy.get("templates", {}).get("allowed_templates"))
        },
        "rate_limit": {
            "enabled": policy.get("rate_limit", {}).get("enabled", False)
        }
    }