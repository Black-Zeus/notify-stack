"""
Policy validator utility
Valida requests contra políticas de seguridad y límites
"""

import re
import logging
from typing import List, Dict, Any, Optional
from email_validator import validate_email, EmailNotValidError

from .config_loader import load_policy_config
from constants import MAX_RECIPIENTS, MAX_ATTACHMENTS, MAX_ATTACHMENT_SIZE


async def validate_request(request) -> None:
    """
    Valida request contra todas las políticas configuradas
    Raises ValueError si alguna política es violada
    """
    
    # Cargar políticas
    policy = load_policy_config()
    
    # Validaciones básicas para EMAIL
    if hasattr(request, 'to'):  # Email request
        await validate_recipients(request.to, request.cc, request.bcc, policy)
        await validate_content_limits(request, policy)
        await validate_whitelist(request.to, request.cc, request.bcc, policy)
        await validate_attachments(request.attachments, policy)
        await validate_template_access(getattr(request, 'template_id', None), policy)
        
        logging.debug(f"Email validation passed for {len(request.to)} recipients")
    
    # Validaciones para SMS/WhatsApp
    elif hasattr(request, 'phone'):  # SMS/WhatsApp request
        await validate_phone_numbers([request.phone], policy)
        await validate_sms_content_limits(request, policy)
        
        logging.debug(f"SMS/WhatsApp validation passed for {request.phone}")
    
    else:
        raise ValueError("Unknown request type - missing 'to' (email) or 'phone' (SMS/WhatsApp)")


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


async def validate_phone_numbers(phones: List[str], policy: Dict[str, Any] = None) -> None:
    """
    Valida números telefónicos para SMS/WhatsApp
    """
    if not policy:
        policy = load_policy_config()
    
    sms_limits = policy.get("sms", {}).get("limits", {})
    max_phone_recipients = sms_limits.get("max_recipients", 10)  # SMS es más limitado que email
    
    if len(phones) > max_phone_recipients:
        raise ValueError(f"Too many SMS/WhatsApp recipients: {len(phones)} (max: {max_phone_recipients})")
    
    for phone in phones:
        if not phone or not phone.strip():
            raise ValueError("Empty phone number found")
        
        # Validación básica de formato E.164
        clean_phone = phone.strip()
        if clean_phone.startswith('whatsapp:'):
            clean_phone = clean_phone.replace('whatsapp:', '')
        
        if not clean_phone.startswith('+'):
            raise ValueError(f"Phone number must be in E.164 format (+1234567890): {phone}")
        
        if len(clean_phone) < 8 or len(clean_phone) > 15:
            raise ValueError(f"Invalid phone number length: {phone}")
        
        # Verificar solo números después del +
        if not clean_phone[1:].isdigit():
            raise ValueError(f"Phone number contains invalid characters: {phone}")
    
    logging.debug(f"Phone numbers validation passed: {len(phones)} numbers")


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
    Valida límites de contenido (subject, body, etc.) para EMAIL
    """
    if not policy:
        policy = load_policy_config()
    
    limits = policy.get("limits", {})
    
    # Validar subject
    if hasattr(request, 'subject') and request.subject:
        max_subject_length = limits.get("max_subject_length", 998)  # RFC 2822 limit
        if len(request.subject) > max_subject_length:
            raise ValueError(f"Subject too long: {len(request.subject)} chars (max: {max_subject_length})")
    
    # Validar body_text
    if hasattr(request, 'body_text') and request.body_text:
        max_body_length = limits.get("max_body_length", 1048576)  # 1MB
        if len(request.body_text) > max_body_length:
            raise ValueError(f"Text body too long: {len(request.body_text)} chars (max: {max_body_length})")
    
    # Validar body_html
    if hasattr(request, 'body_html') and request.body_html:
        max_body_length = limits.get("max_body_length", 1048576)  # 1MB
        if len(request.body_html) > max_body_length:
            raise ValueError(f"HTML body too long: {len(request.body_html)} chars (max: {max_body_length})")
    
    # Validar que hay contenido para email
    if hasattr(request, 'to'):  # Es request de email
        template_id = getattr(request, 'template_id', None)
        body_text = getattr(request, 'body_text', None)
        body_html = getattr(request, 'body_html', None)
        
        if not template_id and not body_text and not body_html:
            raise ValueError("Either template_id or body content (text/html) is required")
    
    logging.debug("Content limits validation passed")


async def validate_sms_content_limits(request, policy: Dict[str, Any] = None) -> None:
    """
    Valida límites de contenido para SMS/WhatsApp
    """
    if not policy:
        policy = load_policy_config()
    
    sms_limits = policy.get("sms", {}).get("limits", {})
    
    # Validar contenido del mensaje
    message = getattr(request, 'message', '')
    if not message or not message.strip():
        # Verificar si usa template
        template_name = getattr(request, 'template_name', None)
        if not template_name:
            raise ValueError("Either message or template_name is required for SMS/WhatsApp")
    else:
        # Validar longitud según el canal
        channel = getattr(request, 'channel', 'sms')
        
        if channel == 'sms':
            max_length = sms_limits.get("max_sms_length", 1600)
        elif channel == 'whatsapp':
            max_length = sms_limits.get("max_whatsapp_length", 4096)
        else:
            max_length = 1600  # Default SMS
        
        if len(message) > max_length:
            raise ValueError(f"{channel.upper()} message too long: {len(message)} chars (max: {max_length})")
    
    logging.debug(f"SMS/WhatsApp content validation passed")


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


async def validate_template_access(template_id: str = None, policy: Dict[str, Any] = None) -> None:
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


async def validate_rate_limit(
    sender_info: Dict[str, Any], 
    channel: str = "email",
    policy: Dict[str, Any] = None
) -> None:
    """
    Valida rate limiting por canal (email/sms/whatsapp)
    TODO: Integrar con Redis para rate limiting real
    """
    if not policy:
        policy = load_policy_config()
    
    # Configuración por canal
    if channel == "email":
        rate_limit_config = policy.get("rate_limit", {})
    else:
        rate_limit_config = policy.get("sms", {}).get("rate_limit", {})
    
    if not rate_limit_config.get("enabled", False):
        return
    
    # Placeholder para implementación real con Redis
    # TODO: Implementar contadores por IP/API key en Redis
    logging.debug(f"Rate limit validation passed (placeholder) for channel: {channel}")


async def validate_security_headers(headers: Dict[str, str], policy: Dict[str, Any] = None) -> None:
    """
    Valida headers de seguridad requeridos
    """
    if not policy:
        policy = load_policy_config()
    
    security_config = policy.get("security", {})
    required_headers = security_config.get("required_headers", [])
    
    for header in required_headers:
        if header not in headers:
            raise ValueError(f"Required security header missing: {header}")
    
    logging.debug("Security headers validation passed")


async def validate_channel_permissions(
    channel: str, 
    api_key: str = None, 
    policy: Dict[str, Any] = None
) -> None:
    """
    Valida permisos por canal (email/sms/whatsapp) según API key
    """
    if not policy:
        policy = load_policy_config()
    
    channel_config = policy.get("channels", {})
    
    # Verificar si el canal está habilitado
    enabled_channels = channel_config.get("enabled", ["email"])
    if channel not in enabled_channels:
        raise ValueError(f"Channel '{channel}' is not enabled. Available: {enabled_channels}")
    
    # TODO: Validar permisos específicos por API key si está configurado
    logging.debug(f"Channel permissions validation passed: {channel}")