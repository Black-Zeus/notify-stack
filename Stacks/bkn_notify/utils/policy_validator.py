"""
Stacks/bkn_notify/utils/policy_validator.py
Policy validator utility
Valida requests contra políticas de seguridad y límites
CON INTEGRACIÓN DE PROVIDER_STATS PARA RECHAZOS
"""

import re
import logging
from typing import List, Dict, Any, Optional
from email_validator import validate_email, EmailNotValidError
from datetime import datetime

from .config_loader import load_policy_config
from constants import MAX_RECIPIENTS, MAX_ATTACHMENTS, MAX_ATTACHMENT_SIZE


# ✅ NUEVA EXCEPCIÓN PARA RECHAZOS CON ESTADÍSTICAS
class NotificationRejectedError(ValueError):
    """
    Excepción específica para notificaciones rechazadas por políticas
    Permite capturar rechazos y actualizar estadísticas
    """
    def __init__(self, message: str, rejection_reason: str, provider: str = None):
        super().__init__(message)
        self.rejection_reason = rejection_reason
        self.provider = provider
        self.rejected_at = datetime.utcnow()


async def validate_request(request, provider: str = None) -> None:
    """
    Valida request contra todas las políticas configuradas
    
    Args:
        request: Objeto request a validar
        provider: Proveedor que procesaría la notificación (para estadísticas)
    
    Raises:
        NotificationRejectedError: Si alguna política es violada
    """
    
    # Cargar políticas
    policy = load_policy_config()
    
    try:
        # Validaciones básicas para EMAIL
        if hasattr(request, 'to') and hasattr(request, 'cc'):  # Email request
            await validate_recipients(request.to, request.cc, request.bcc, policy, provider)
            await validate_content_limits(request, policy, provider)
            await validate_whitelist(request.to, request.cc, request.bcc, policy, provider)
            await validate_attachments(getattr(request, 'attachments', None), policy, provider)
            await validate_template_access(getattr(request, 'template_id', None), policy, provider)
            
            logging.debug(f"Email validation passed for {len(request.to)} recipients")
        
        # Validaciones para SMS/WhatsApp (Twilio)
        elif hasattr(request, 'to') and not hasattr(request, 'cc'):  # Twilio request
            await validate_phone_numbers(request.to, policy, provider)
            await validate_sms_content_limits(request, policy, provider)
            
            logging.debug(f"SMS/WhatsApp validation passed for {len(request.to)} recipients")
        
        # Validaciones legacy para SMS/WhatsApp con campo 'phone'
        elif hasattr(request, 'phone'):  # SMS/WhatsApp request legacy
            await validate_phone_numbers([request.phone], policy, provider)
            await validate_sms_content_limits(request, policy, provider)
            
            logging.debug(f"SMS/WhatsApp validation passed for {request.phone}")
        
        else:
            raise NotificationRejectedError(
                "Unknown request type - missing 'to' (email) or 'phone' (SMS/WhatsApp)",
                "invalid_request_format",
                provider
            )
            
    except ValueError as e:
        # Convertir ValueError genérico a NotificationRejectedError
        if isinstance(e, NotificationRejectedError):
            raise  # Re-raise si ya es el tipo correcto
        else:
            raise NotificationRejectedError(
                str(e),
                "validation_error",
                provider
            )


async def validate_recipients(
    to: List[str], 
    cc: List[str] = None, 
    bcc: List[str] = None, 
    policy: Dict[str, Any] = None, 
    provider: str = None
) -> None:
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
        raise NotificationRejectedError(
            "At least one recipient (to, cc, or bcc) is required",
            "no_recipients",
            provider
        )
    
    # Verificar límite de destinatarios
    max_recipients = policy.get("limits", {}).get("max_recipients", MAX_RECIPIENTS)
    if len(all_recipients) > max_recipients:
        raise NotificationRejectedError(
            f"Too many recipients: {len(all_recipients)} (max: {max_recipients})",
            "too_many_recipients",
            provider
        )
    
    # Validar formato de cada email
    unique_recipients = set()
    for email in all_recipients:
        if not email or not email.strip():
            raise NotificationRejectedError(
                "Empty email address found",
                "empty_email",
                provider
            )
        
        email = email.strip().lower()
        
        # Verificar duplicados
        if email in unique_recipients:
            logging.warning(f"Duplicate recipient found: {email}")
        unique_recipients.add(email)
        
        # Validar formato de email
        try:
            validate_email(email)
        except EmailNotValidError as e:
            raise NotificationRejectedError(
                f"Invalid email address '{email}': {str(e)}",
                "invalid_email_format",
                provider
            )
    
    logging.debug(f"Recipients validation passed: {len(unique_recipients)} unique emails")


async def validate_phone_numbers(
    phones: List[str], 
    policy: Dict[str, Any] = None, 
    provider: str = None
) -> None:
    """
    Valida números telefónicos para SMS/WhatsApp
    """
    if not policy:
        policy = load_policy_config()
    
    sms_limits = policy.get("sms", {}).get("limits", {})
    max_phone_recipients = sms_limits.get("max_recipients", 10)  # SMS es más limitado que email
    
    if len(phones) > max_phone_recipients:
        raise NotificationRejectedError(
            f"Too many SMS/WhatsApp recipients: {len(phones)} (max: {max_phone_recipients})",
            "too_many_phone_recipients",
            provider
        )
    
    for phone in phones:
        if not phone or not phone.strip():
            raise NotificationRejectedError(
                "Empty phone number found",
                "empty_phone_number",
                provider
            )
        
        # Validación básica de formato E.164
        clean_phone = phone.strip()
        if clean_phone.startswith('whatsapp:'):
            clean_phone = clean_phone.replace('whatsapp:', '')
        
        if not clean_phone.startswith('+'):
            raise NotificationRejectedError(
                f"Phone number must be in E.164 format (+1234567890): {phone}",
                "invalid_phone_format",
                provider
            )
        
        if len(clean_phone) < 8 or len(clean_phone) > 15:
            raise NotificationRejectedError(
                f"Invalid phone number length: {phone}",
                "invalid_phone_length",
                provider
            )
        
        # Verificar solo números después del +
        if not clean_phone[1:].isdigit():
            raise NotificationRejectedError(
                f"Phone number contains invalid characters: {phone}",
                "invalid_phone_characters",
                provider
            )
    
    logging.debug(f"Phone numbers validation passed: {len(phones)} numbers")


async def validate_whitelist(
    to: List[str], 
    cc: List[str] = None, 
    bcc: List[str] = None, 
    policy: Dict[str, Any] = None, 
    provider: str = None
) -> None:
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
            raise NotificationRejectedError(
                f"Domain '{domain}' not in whitelist. Allowed domains: {allowed_domains}",
                "domain_not_whitelisted",
                provider
            )
    
    logging.debug(f"Whitelist validation passed for {len(all_recipients)} recipients")


async def validate_content_limits(
    request, 
    policy: Dict[str, Any] = None, 
    provider: str = None
) -> None:
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
            raise NotificationRejectedError(
                f"Subject too long: {len(request.subject)} chars (max: {max_subject_length})",
                "subject_too_long",
                provider
            )
    
    # Validar body_text
    if hasattr(request, 'body_text') and request.body_text:
        max_body_length = limits.get("max_body_length", 1048576)  # 1MB
        if len(request.body_text) > max_body_length:
            raise NotificationRejectedError(
                f"Text body too long: {len(request.body_text)} chars (max: {max_body_length})",
                "body_text_too_long",
                provider
            )
    
    # Validar body_html
    if hasattr(request, 'body_html') and request.body_html:
        max_body_length = limits.get("max_body_length", 1048576)  # 1MB
        if len(request.body_html) > max_body_length:
            raise NotificationRejectedError(
                f"HTML body too long: {len(request.body_html)} chars (max: {max_body_length})",
                "body_html_too_long",
                provider
            )
    
    # Validar que hay contenido para email
    if hasattr(request, 'to'):  # Es request de email
        template_id = getattr(request, 'template_id', None)
        body_text = getattr(request, 'body_text', None)
        body_html = getattr(request, 'body_html', None)
        
        if not template_id and not body_text and not body_html:
            raise NotificationRejectedError(
                "Either template_id or body content (text/html) is required",
                "missing_content",
                provider
            )
    
    logging.debug("Content limits validation passed")


async def validate_sms_content_limits(
    request, 
    policy: Dict[str, Any] = None, 
    provider: str = None
) -> None:
    """
    Valida límites de contenido para SMS/WhatsApp
    """
    if not policy:
        policy = load_policy_config()
    
    sms_limits = policy.get("sms", {}).get("limits", {})
    
    # ✅ CORREGIDO: Buscar mensaje en diferentes campos según el modelo
    message = None
    template_id = None
    
    # TwilioNotifyRequest usa 'body_text' y 'template_id'
    if hasattr(request, 'body_text'):
        message = getattr(request, 'body_text', '')
        template_id = getattr(request, 'template_id', None)
    # Modelo legacy con 'message' y 'template_name'
    elif hasattr(request, 'message'):
        message = getattr(request, 'message', '')
        template_id = getattr(request, 'template_name', None)
    
    # Validar que hay contenido
    if not message or not message.strip():
        # Verificar si usa template
        if not template_id:
            raise NotificationRejectedError(
                "Either body_text/message or template_id/template_name is required for SMS/WhatsApp",
                "missing_sms_content",
                provider
            )
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
            raise NotificationRejectedError(
                f"{channel.upper()} message too long: {len(message)} chars (max: {max_length})",
                "sms_message_too_long",
                provider
            )
    
    logging.debug(f"SMS/WhatsApp content validation passed")


async def validate_attachments(
    attachments: List[Dict] = None, 
    policy: Dict[str, Any] = None, 
    provider: str = None
) -> None:
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
        raise NotificationRejectedError(
            f"Too many attachments: {len(attachments)} (max: {max_attachments})",
            "too_many_attachments",
            provider
        )
    
    # Verificar cada attachment
    max_attachment_size = limits.get("max_attachment_size", MAX_ATTACHMENT_SIZE)
    total_size = 0
    
    for i, attachment in enumerate(attachments):
        if not isinstance(attachment, dict):
            raise NotificationRejectedError(
                f"Attachment {i}: invalid format, must be object",
                "invalid_attachment_format",
                provider
            )
        
        # Verificar campos requeridos
        if "filename" not in attachment:
            raise NotificationRejectedError(
                f"Attachment {i}: filename is required",
                "missing_attachment_filename",
                provider
            )
        
        if "content" not in attachment:
            raise NotificationRejectedError(
                f"Attachment {i}: content is required",
                "missing_attachment_content",
                provider
            )
        
        # Verificar nombre de archivo
        filename = attachment["filename"]
        if not filename or not filename.strip():
            raise NotificationRejectedError(
                f"Attachment {i}: filename cannot be empty",
                "empty_attachment_filename",
                provider
            )
        
        # Verificar caracteres peligrosos en filename
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
        if any(char in filename for char in dangerous_chars):
            raise NotificationRejectedError(
                f"Attachment {i}: filename contains dangerous characters",
                "dangerous_attachment_filename",
                provider
            )
        
        # Verificar tamaño (asumiendo base64)
        content_size = len(attachment["content"])
        if content_size > max_attachment_size:
            raise NotificationRejectedError(
                f"Attachment {i} too large: {content_size} bytes (max: {max_attachment_size})",
                "attachment_too_large",
                provider
            )
        
        total_size += content_size
    
    # Verificar tamaño total
    max_total_size = limits.get("max_total_attachments_size", max_attachment_size * max_attachments)
    if total_size > max_total_size:
        raise NotificationRejectedError(
            f"Total attachments size too large: {total_size} bytes (max: {max_total_size})",
            "total_attachments_too_large",
            provider
        )
    
    logging.debug(f"Attachments validation passed: {len(attachments)} files, {total_size} bytes")


async def validate_template_access(
    template_id: str = None, 
    policy: Dict[str, Any] = None, 
    provider: str = None
) -> None:
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
        raise NotificationRejectedError(
            f"Template '{template_id}' not in allowed list: {allowed_templates}",
            "template_not_allowed",
            provider
        )
    
    # Verificar patrones bloqueados
    blocked_patterns = template_policy.get("blocked_patterns", [])
    for pattern in blocked_patterns:
        if re.match(pattern, template_id):
            raise NotificationRejectedError(
                f"Template '{template_id}' matches blocked pattern: {pattern}",
                "template_blocked_pattern",
                provider
            )
    
    logging.debug(f"Template access validation passed: {template_id}")


# ✅ FUNCIONES MANTENIDAS SIN CAMBIOS (no necesitan provider para estadísticas)

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