"""
Modelo Pydantic específico para notificaciones Twilio (WhatsApp/SMS)
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import re


class TwilioNotifyRequest(BaseModel):
    """
    Modelo para requests de notificación Twilio (WhatsApp/SMS)
    """
    
    # Destinatarios (números de teléfono)
    to: List[str] = Field(..., min_length=1, max_length=10, description="Números de teléfono destinatarios")
    
    # Contenido
    template_id: Optional[str] = Field(default=None, max_length=100, description="ID del template a usar")
    body_text: Optional[str] = Field(default=None, max_length=1600, description="Mensaje directo (WhatsApp: 1600 chars, SMS: 160)")
    
    # Variables para templates
    vars: Optional[Dict[str, Any]] = Field(default=None, description="Variables para el template")
    
    # Configuración
    provider: Optional[str] = Field(default=None, description="Proveedor específico (twilio_sms, twilio_whatsapp)")
    routing_hint: Optional[str] = Field(default=None, description="Hint para routing")
    
    # Headers/opciones personalizadas
    custom_options: Optional[Dict[str, Any]] = Field(default=None, description="Opciones específicas del proveedor")
    
    @field_validator('to')
    @classmethod
    def validate_phone_numbers(cls, v):
        """Valida formato de números de teléfono"""
        validated_numbers = []
        
        for phone in v:
            phone = phone.strip()
            
            # Formato internacional requerido
            if not phone.startswith('+'):
                raise ValueError(f"Phone number must include country code: {phone}")
            
            # Solo números después del +
            if not re.match(r'^\+\d{8,15}$', phone):
                raise ValueError(f"Invalid phone number format: {phone} (must be +[country][number])")
            
            # Verificar longitud típica
            if len(phone) < 10 or len(phone) > 16:
                raise ValueError(f"Phone number length invalid: {phone}")
            
            validated_numbers.append(phone)
        
        # Eliminar duplicados manteniendo orden
        seen = set()
        unique_numbers = []
        for phone in validated_numbers:
            if phone not in seen:
                seen.add(phone)
                unique_numbers.append(phone)
        
        return unique_numbers
    
    @field_validator('body_text')
    @classmethod
    def validate_message_length(cls, v):
        """Valida longitud del mensaje según el tipo"""
        if v is None:
            return v
        
        # WhatsApp permite hasta 4096 caracteres pero recomendamos 1600
        if len(v) > 1600:
            raise ValueError(f"Message too long: {len(v)} characters (max: 1600)")
        
        # Verificar caracteres especiales problemáticos
        if '\x00' in v:
            raise ValueError("Message contains null characters")
        
        return v.strip()
    
    @field_validator('template_id')
    @classmethod
    def validate_template_format(cls, v):
        """Valida formato del template ID"""
        if not v:
            return v
            
        import re
        
        # Convertir punto a slash (cert-summary.v1 -> cert-summary/v1)
        if '.' in v and 'v' in v:
            v = re.sub(r'\.v(\d+)$', r'/v\1', v)
        
        # Validar formato final
        if not re.match(r'^[a-zA-Z0-9\-_]+/v\d+$', v):
            raise ValueError("template_id must follow format: template-name/vN")
        
        return v
    
    @field_validator('provider')
    @classmethod
    def validate_provider_type(cls, v):
        """Valida que sea un proveedor Twilio válido"""
        if v is None:
            return v
        
        valid_providers = ['twilio_sms', 'twilio_whatsapp', 'twilio']
        if v not in valid_providers:
            raise ValueError(f"Invalid Twilio provider: {v}. Must be one of: {', '.join(valid_providers)}")
        
        return v
    
    @field_validator('routing_hint')
    @classmethod
    def validate_routing_hint(cls, v):
        """Valida routing hint"""
        if v is None:
            return v
        
        valid_hints = [
            'high_priority', 'urgent', 'marketing', 'transactional', 
            'otp', 'notification', 'alert', 'reminder'
        ]
        
        if v not in valid_hints:
            raise ValueError(f"Invalid routing_hint. Must be one of: {', '.join(valid_hints)}")
        
        return v
    
    @model_validator(mode='after')
    def validate_content_or_template(self):
        """Valida que hay contenido o template"""
        if not self.template_id and not self.body_text:
            raise ValueError("Either template_id or body_text is required")
        
        if self.template_id and self.body_text:
            raise ValueError("Cannot specify both template_id and body_text")
        
        return self
    
    @model_validator(mode='after')
    def validate_template_variables(self):
        """Valida variables si se usa template"""
        if self.template_id and not self.vars:
            # Warning: debería haber variables para la mayoría de templates
            pass
        
        return self
    
    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True,
        "extra": "forbid",
        "json_schema_extra": {
            "examples": [
                {
                    "description": "WhatsApp con template",
                    "value": {
                        "to": ["+56912345678"],
                        "template_id": "alerta-simple/v1",
                        "provider": "twilio_whatsapp",
                        "vars": {
                            "host": "web-server-01",
                            "estado": "CRÍTICO",
                            "hora": "15:30",
                            "timestamp": "2024-09-16 15:30:45"
                        }
                    }
                },
                {
                    "description": "SMS directo",
                    "value": {
                        "to": ["+56912345678", "+56987654321"],
                        "body_text": "ALERTA: Servidor web-server-01 está CRÍTICO desde las 15:30. Revisar inmediatamente.",
                        "provider": "twilio_sms",
                        "routing_hint": "urgent"
                    }
                },
                {
                    "description": "WhatsApp con múltiples destinatarios",
                    "value": {
                        "to": ["+56987654321", "+56912345678"],
                        "template_id": "system-alert/v1",
                        "provider": "twilio_whatsapp",
                        "routing_hint": "high_priority",
                        "vars": {
                            "servidor": "prod-api-01",
                            "tipo_alerta": "espacio_disco",
                            "severidad": "high",
                            "uso_disco": 92
                        }
                    }
                }
            ]
        }
    }