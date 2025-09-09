"""
Pydantic models for notification requests and responses
Esquemas de validación para el sistema de notificaciones
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator, root_validator
from datetime import datetime


class AttachmentModel(BaseModel):
    """
    Modelo para attachments de email
    """
    filename: str = Field(..., min_length=1, max_length=255, description="Nombre del archivo")
    content: str = Field(..., description="Contenido del archivo en base64")
    content_type: Optional[str] = Field(default="application/octet-stream", description="MIME type del archivo")
    
    @validator('filename')
    def validate_filename(cls, v):
        """Valida nombre de archivo seguro"""
        # Caracteres peligrosos
        dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*', '\x00']
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Filename contains dangerous character: {char}")
        
        # Verificar extensión
        if not '.' in v:
            raise ValueError("Filename must have an extension")
        
        return v.strip()
    
    @validator('content')
    def validate_content(cls, v):
        """Valida contenido base64"""
        import base64
        try:
            # Verificar que es base64 válido
            base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("Content must be valid base64")
        
        # Verificar tamaño (5MB max)
        if len(v) > 6710886:  # 5MB en base64 ≈ 6.7MB
            raise ValueError("Attachment too large (max 5MB)")
        
        return v


class NotifyRequest(BaseModel):
    """
    Modelo para request de notificación
    """
    
    # Destinatarios (requerido)
    to: List[EmailStr] = Field(..., min_items=1, max_items=100, description="Destinatarios principales")
    cc: Optional[List[EmailStr]] = Field(default=None, max_items=50, description="Destinatarios en copia")
    bcc: Optional[List[EmailStr]] = Field(default=None, max_items=50, description="Destinatarios en copia oculta")
    
    # Contenido
    subject: Optional[str] = Field(default=None, max_length=998, description="Asunto del email")
    template_id: Optional[str] = Field(default=None, max_length=100, description="ID del template a usar")
    body_text: Optional[str] = Field(default=None, max_length=1048576, description="Cuerpo en texto plano")
    body_html: Optional[str] = Field(default=None, max_length=1048576, description="Cuerpo en HTML")
    
    # Variables para templates
    vars: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variables para el template")
    
    # Attachments
    attachments: Optional[List[AttachmentModel]] = Field(default=None, max_items=10, description="Archivos adjuntos")
    
    # Configuración de envío
    provider: Optional[str] = Field(default=None, max_length=50, description="Proveedor específico a usar")
    routing_hint: Optional[str] = Field(default=None, max_length=50, description="Hint para routing")
    
    # Headers personalizados
    custom_headers: Optional[Dict[str, str]] = Field(default=None, description="Headers HTTP personalizados")
    
    @root_validator
    def validate_content_requirements(cls, values):
        """Valida que hay contenido suficiente para el email"""
        template_id = values.get('template_id')
        subject = values.get('subject')
        body_text = values.get('body_text')
        body_html = values.get('body_html')
        
        # Si usa template, no necesita otros campos obligatorios
        if template_id:
            return values
        
        # Si no usa template, necesita subject y al menos un body
        if not subject:
            raise ValueError("subject is required when not using template_id")
        
        if not body_text and not body_html:
            raise ValueError("Either body_text or body_html is required when not using template_id")
        
        return values
    
    @validator('to', 'cc', 'bcc')
    def validate_email_lists(cls, v):
        """Valida listas de emails y elimina duplicados"""
        if not v:
            return v
        
        # Normalizar y eliminar duplicados manteniendo orden
        seen = set()
        unique_emails = []
        for email in v:
            email_lower = str(email).lower()
            if email_lower not in seen:
                seen.add(email_lower)
                unique_emails.append(email)
        
        return unique_emails
    
    @root_validator
    def validate_total_recipients(cls, values):
        """Valida límite total de destinatarios"""
        to = values.get('to', [])
        cc = values.get('cc', [])
        bcc = values.get('bcc', [])
        
        total_recipients = len(to) + len(cc or []) + len(bcc or [])
        
        if total_recipients > 150:  # Límite total más generoso
            raise ValueError(f"Too many total recipients: {total_recipients} (max: 150)")
        
        return values
    
    @validator('subject')
    def validate_subject(cls, v):
        """Valida subject"""
        if v is None:
            return v
        
        # Remover caracteres de control
        import re
        if re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', v):
            raise ValueError("Subject contains control characters")
        
        # Normalizar espacios
        normalized = re.sub(r'\s+', ' ', v.strip())
        
        return normalized
    
    @validator('template_id')
    def validate_template_id(cls, v):
        """Valida formato de template ID"""
        if v is None:
            return v
        
        # Formato esperado: nombre/version (ej: "alerta-simple/v1")
        import re
        if not re.match(r'^[a-zA-Z0-9\-_]+/v\d+$', v):
            raise ValueError("template_id must follow format: template-name/vN (e.g., 'alert-simple/v1')")
        
        return v
    
    @validator('provider')
    def validate_provider(cls, v):
        """Valida nombre de proveedor"""
        if v is None:
            return v
        
        # Solo caracteres alfanuméricos, guiones y guiones bajos
        import re
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
            raise ValueError("provider name can only contain letters, numbers, hyphens and underscores")
        
        return v
    
    @validator('routing_hint')
    def validate_routing_hint(cls, v):
        """Valida routing hint"""
        if v is None:
            return v
        
        valid_hints = [
            'high_priority', 'bulk', 'transactional', 'marketing', 
            'test', 'urgent', 'low_priority', 'newsletter'
        ]
        
        if v not in valid_hints:
            raise ValueError(f"Invalid routing_hint. Must be one of: {', '.join(valid_hints)}")
        
        return v
    
    @validator('custom_headers')
    def validate_custom_headers(cls, v):
        """Valida headers personalizados"""
        if not v:
            return v
        
        # Verificar que no hay headers reservados
        reserved_headers = {
            'from', 'to', 'cc', 'bcc', 'subject', 'date', 'message-id',
            'return-path', 'reply-to', 'content-type', 'mime-version'
        }
        
        for header_name in v.keys():
            if header_name.lower() in reserved_headers:
                raise ValueError(f"Cannot override reserved header: {header_name}")
        
        # Validar formato de headers
        import re
        for name, value in v.items():
            if not re.match(r'^[a-zA-Z0-9\-_]+$', name):
                raise ValueError(f"Invalid header name: {name}")
            
            if len(str(value)) > 998:  # RFC limit
                raise ValueError(f"Header value too long: {name}")
        
        return v
    
    class Config:
        """Configuración del modelo Pydantic"""
        str_strip_whitespace = True
        validate_assignment = True
        use_enum_values = True
        extra = "forbid"  # No permitir campos adicionales
        
        schema_extra = {
            "example": {
                "to": ["user@example.com"],
                "cc": ["manager@example.com"],
                "subject": "Welcome to our service",
                "template_id": "welcome-email/v1",
                "vars": {
                    "user_name": "John Doe",
                    "activation_link": "https://example.com/activate/123"
                },
                "routing_hint": "transactional"
            }
        }


class NotifyResponse(BaseModel):
    """
    Modelo para respuesta de notificación
    """
    message_id: str = Field(..., description="ID único del mensaje para tracking")
    status: str = Field(..., description="Estado inicial: 'accepted', 'rejected'")
    celery_task_id: str = Field(..., description="ID de la tarea Celery para seguimiento")
    provider: Optional[str] = Field(default=None, description="Proveedor seleccionado para el envío")
    estimated_delivery: Optional[str] = Field(default="immediate", description="Tiempo estimado de entrega")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Timestamp de creación")
    
    class Config:
        schema_extra = {
            "example": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "accepted",
                "celery_task_id": "b64c73fc-6b25-42b2-aa52-512c7a3b7cc8",
                "provider": "smtp_primary",
                "estimated_delivery": "immediate",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


class BulkNotifyRequest(BaseModel):
    """
    Modelo para envío masivo de notificaciones
    """
    template_id: str = Field(..., description="Template común para todos los envíos")
    recipients: List[Dict[str, Any]] = Field(..., min_items=1, max_items=1000, description="Lista de destinatarios con sus variables")
    common_vars: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variables comunes para todos")
    provider: Optional[str] = Field(default=None, description="Proveedor específico")
    routing_hint: Optional[str] = Field(default="bulk", description="Hint de routing")
    
    @validator('recipients')
    def validate_recipients(cls, v):
        """Valida estructura de destinatarios"""
        for i, recipient in enumerate(v):
            if 'email' not in recipient:
                raise ValueError(f"Recipient {i} missing required 'email' field")
            
            # Validar email
            from pydantic import EmailStr
            try:
                EmailStr.validate(recipient['email'])
            except Exception:
                raise ValueError(f"Invalid email in recipient {i}: {recipient['email']}")
        
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "template_id": "newsletter/v2",
                "recipients": [
                    {
                        "email": "user1@example.com",
                        "name": "John Doe",
                        "preferences": {"topic": "tech"}
                    },
                    {
                        "email": "user2@example.com", 
                        "name": "Jane Smith",
                        "preferences": {"topic": "business"}
                    }
                ],
                "common_vars": {
                    "company_name": "Acme Corp",
                    "month": "January 2024"
                },
                "routing_hint": "bulk"
            }
        }


class BulkNotifyResponse(BaseModel):
    """
    Respuesta para envío masivo
    """
    batch_id: str = Field(..., description="ID del lote para tracking")
    status: str = Field(..., description="Estado del lote")
    total_recipients: int = Field(..., description="Total de destinatarios")
    celery_task_ids: List[str] = Field(..., description="IDs de todas las tareas Celery creadas")
    estimated_completion: Optional[str] = Field(default=None, description="Tiempo estimado de finalización")
    
    class Config:
        schema_extra = {
            "example": {
                "batch_id": "batch_550e8400-e29b-41d4-a716-446655440000",
                "status": "accepted",
                "total_recipients": 1000,
                "celery_task_ids": ["task_1", "task_2", "task_3"],
                "estimated_completion": "5 minutes"
            }
        }