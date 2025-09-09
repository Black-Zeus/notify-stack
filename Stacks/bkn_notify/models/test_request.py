"""
Pydantic models for testing endpoints
Esquemas para endpoints de testing y validación del sistema
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from enum import Enum

from .notify_request import AttachmentModel  # Reutilizar modelo de attachments


class TestType(str, Enum):
    """
    Tipos de test disponibles
    """
    SEND = "send"                    # Test de envío completo
    CONNECTIVITY = "connectivity"    # Test de conectividad únicamente
    TEMPLATE = "template"           # Test de renderizado de template
    VALIDATION = "validation"       # Test de validación sin envío


class ConnectivityStatus(str, Enum):
    """
    Estados de conectividad
    """
    HEALTHY = "healthy"         # Funcionando correctamente
    DEGRADED = "degraded"       # Funcionando pero con problemas
    ERROR = "error"            # No funciona
    NOT_IMPLEMENTED = "not_implemented"  # Tipo no implementado


class TestRequest(BaseModel):
    """
    Request para test de envío de notificación
    """
    # Proveedor a probar (requerido)
    provider: str = Field(..., max_length=50, description="Nombre del proveedor a probar")
    
    # Destinatarios (opcional, usa defaults si no se especifica)
    to: Optional[List[EmailStr]] = Field(default=None, max_items=5, description="Destinatarios de prueba")
    cc: Optional[List[EmailStr]] = Field(default=None, max_items=3, description="CC de prueba")
    bcc: Optional[List[EmailStr]] = Field(default=None, max_items=3, description="BCC de prueba")
    
    # Contenido del test
    subject: Optional[str] = Field(default=None, max_length=200, description="Subject personalizado")
    template_id: Optional[str] = Field(default=None, max_length=100, description="Template a probar")
    body_text: Optional[str] = Field(default=None, max_length=10000, description="Cuerpo en texto")
    body_html: Optional[str] = Field(default=None, max_length=20000, description="Cuerpo en HTML")
    
    # Variables para template
    vars: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variables de prueba")
    
    # Attachments de prueba
    attachments: Optional[List[AttachmentModel]] = Field(default=None, max_items=3, description="Attachments de prueba")
    
    # Configuración del test
    skip_validation: bool = Field(default=False, description="Omitir validaciones de política")
    timeout: Optional[int] = Field(default=30, ge=5, le=300, description="Timeout en segundos")
    
    @validator('provider')
    def validate_provider_name(cls, v):
        """Valida nombre del proveedor"""
        import re
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
            raise ValueError("Provider name can only contain letters, numbers, hyphens and underscores")
        return v
    
    @validator('to', 'cc', 'bcc')
    def validate_test_recipients(cls, v):
        """Valida que no sean demasiados destinatarios para test"""
        if v and len(v) > 5:
            raise ValueError("Too many recipients for test (max 5 per field)")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "provider": "smtp_primary",
                "to": ["test@example.com"],
                "subject": "Test Email - Notify API",
                "template_id": "welcome-email/v1",
                "vars": {
                    "user_name": "Test User",
                    "test_mode": True
                },
                "timeout": 30
            }
        }


class TestResponse(BaseModel):
    """
    Respuesta del test de envío
    """
    test_id: str = Field(..., description="ID único del test")
    status: str = Field(..., description="Estado del test: accepted, rejected")
    celery_task_id: str = Field(..., description="ID de la tarea Celery del test")
    provider: str = Field(..., description="Proveedor utilizado")
    recipients: List[str] = Field(..., description="Destinatarios finales del test")
    message: str = Field(..., description="Mensaje descriptivo del resultado")
    
    # Metadata del test
    test_type: TestType = Field(default=TestType.SEND, description="Tipo de test realizado")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp del test")
    
    class Config:
        use_enum_values = True
        schema_extra = {
            "example": {
                "test_id": "test_550e8400-e29b-41d4-a716-446655440000",
                "status": "accepted",
                "celery_task_id": "test_task_b64c73fc-6b25-42b2-aa52-512c7a3b7cc8",
                "provider": "smtp_primary",
                "recipients": ["test@example.com"],
                "message": "Test notification queued successfully",
                "test_type": "send",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


class ConnectivityTestRequest(BaseModel):
    """
    Request para test de conectividad
    """
    provider: Optional[str] = Field(default=None, description="Proveedor específico a probar (opcional)")
    timeout: int = Field(default=10, ge=1, le=60, description="Timeout de conexión en segundos")
    deep_check: bool = Field(default=False, description="Realizar verificación profunda (más lenta)")
    
    class Config:
        schema_extra = {
            "example": {
                "provider": "smtp_primary",
                "timeout": 15,
                "deep_check": True
            }
        }


class ProviderTestResult(BaseModel):
    """
    Resultado de test para un proveedor específico
    """
    provider_name: str = Field(..., description="Nombre del proveedor")
    status: ConnectivityStatus = Field(..., description="Estado de la conectividad")
    message: str = Field(..., description="Mensaje descriptivo del resultado")
    response_time: float = Field(default=0.0, description="Tiempo de respuesta en segundos")
    
    # Detalles técnicos
    details: Optional[Dict[str, Any]] = Field(default=None, description="Detalles técnicos del test")
    capabilities: Optional[Dict[str, bool]] = Field(default=None, description="Capacidades detectadas")
    
    # Información de error si aplica
    error_type: Optional[str] = Field(default=None, description="Tipo de error si falló")
    error_message: Optional[str] = Field(default=None, description="Mensaje de error detallado")
    
    @validator('response_time')
    def validate_response_time(cls, v):
        """Valida tiempo de respuesta"""
        if v < 0:
            return 0.0
        return round(v, 3)
    
    class Config:
        use_enum_values = True
        schema_extra = {
            "example": {
                "provider_name": "smtp_primary",
                "status": "healthy",
                "message": "SMTP server smtp.gmail.com:587 is accessible and authenticated",
                "response_time": 1.234,
                "details": {
                    "tcp_connection": {"success": True},
                    "smtp_connection": {"success": True},
                    "starttls": {"success": True},
                    "authentication": {"success": True, "username": "notifications@company.com"}
                },
                "capabilities": {
                    "supports_tls": True,
                    "supports_auth": True,
                    "supports_size": True,
                    "max_message_size": 25165824
                }
            }
        }


class ConnectivityTestResponse(BaseModel):
    """
    Respuesta completa del test de conectividad
    """
    overall_status: ConnectivityStatus = Field(..., description="Estado general de todos los proveedores")
    providers_tested: int = Field(..., description="Número de proveedores probados")
    results: Dict[str, ProviderTestResult] = Field(..., description="Resultados por proveedor")
    tested_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp del test")
    
    # Estadísticas generales
    healthy_count: Optional[int] = Field(default=None, description="Proveedores en estado healthy")
    degraded_count: Optional[int] = Field(default=None, description="Proveedores en estado degraded")
    error_count: Optional[int] = Field(default=None, description="Proveedores en estado error")
    average_response_time: Optional[float] = Field(default=None, description="Tiempo promedio de respuesta")
    
    @validator('results')
    def calculate_statistics(cls, v, values):
        """Calcula estadísticas automáticamente"""
        if not v:
            return v
        
        # Contar estados
        healthy = sum(1 for result in v.values() if result.status == ConnectivityStatus.HEALTHY)
        degraded = sum(1 for result in v.values() if result.status == ConnectivityStatus.DEGRADED)
        error = sum(1 for result in v.values() if result.status == ConnectivityStatus.ERROR)
        
        # Calcular tiempo promedio
        response_times = [result.response_time for result in v.values() if result.response_time > 0]
        avg_time = sum(response_times) / len(response_times) if response_times else 0.0
        
        # Actualizar valores (en un validador real esto no se puede hacer directamente)
        # Pero lo documentamos para que se haga en la lógica de negocio
        
        return v
    
    class Config:
        use_enum_values = True
        schema_extra = {
            "example": {
                "overall_status": "healthy",
                "providers_tested": 2,
                "results": {
                    "smtp_primary": {
                        "provider_name": "smtp_primary",
                        "status": "healthy",
                        "message": "SMTP server accessible and authenticated",
                        "response_time": 1.234
                    },
                    "api_sendgrid": {
                        "provider_name": "api_sendgrid",
                        "status": "healthy",
                        "message": "SendGrid API accessible",
                        "response_time": 0.856
                    }
                },
                "tested_at": "2024-01-15T10:30:00Z",
                "healthy_count": 2,
                "degraded_count": 0,
                "error_count": 0,
                "average_response_time": 1.045
            }
        }


class TemplateTestRequest(BaseModel):
    """
    Request para test de renderizado de template
    """
    template_id: str = Field(..., max_length=100, description="ID del template a probar")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variables para el template")
    validate_syntax: bool = Field(default=True, description="Validar sintaxis del template")
    
    @validator('template_id')
    def validate_template_format(cls, v):
        """Valida formato del template ID"""
        import re
        if not re.match(r'^[a-zA-Z0-9\-_]+/v\d+$', v):
            raise ValueError("template_id must follow format: template-name/vN")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "template_id": "welcome-email/v1",
                "variables": {
                    "user_name": "John Doe",
                    "company_name": "Acme Corp",
                    "activation_url": "https://example.com/activate/123"
                },
                "validate_syntax": True
            }
        }


class TemplateTestResponse(BaseModel):
    """
    Respuesta del test de template
    """
    template_id: str = Field(..., description="ID del template probado")
    status: str = Field(..., description="Estado del test: success, error")
    
    # Contenido renderizado
    rendered_content: Optional[Dict[str, str]] = Field(default=None, description="Contenido renderizado")
    
    # Validación de sintaxis
    syntax_validation: Optional[Dict[str, Any]] = Field(default=None, description="Resultado de validación de sintaxis")
    
    # Variables utilizadas
    variables_used: Dict[str, Any] = Field(..., description="Variables utilizadas en el renderizado")
    
    # Metadata
    rendering_time: Optional[float] = Field(default=None, description="Tiempo de renderizado en segundos")
    tested_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp del test")
    
    # Errores si los hay
    errors: Optional[List[str]] = Field(default=None, description="Lista de errores encontrados")
    warnings: Optional[List[str]] = Field(default=None, description="Lista de advertencias")
    
    class Config:
        schema_extra = {
            "example": {
                "template_id": "welcome-email/v1",
                "status": "success",
                "rendered_content": {
                    "subject": "Welcome to Acme Corp, John Doe!",
                    "body_text": "Hello John Doe,\n\nWelcome to Acme Corp...",
                    "body_html": "<h1>Welcome to Acme Corp, John Doe!</h1><p>Hello John Doe,</p>"
                },
                "syntax_validation": {
                    "subject": {"valid": True},
                    "body_text": {"valid": True},
                    "body_html": {"valid": True}
                },
                "variables_used": {
                    "user_name": "John Doe",
                    "company_name": "Acme Corp"
                },
                "rendering_time": 0.045,
                "tested_at": "2024-01-15T10:30:00Z"
            }
        }


class ValidationTestRequest(BaseModel):
    """
    Request para test de validación sin envío
    """
    # Datos a validar
    to: List[EmailStr] = Field(..., min_items=1, max_items=10, description="Emails a validar")
    subject: Optional[str] = Field(default=None, description="Subject a validar")
    content: Optional[str] = Field(default=None, description="Contenido a validar")
    
    # Tipos de validación
    check_format: bool = Field(default=True, description="Validar formato de email")
    check_deliverability: bool = Field(default=False, description="Validar deliverability")
    check_mx: bool = Field(default=False, description="Validar registros MX")
    check_disposable: bool = Field(default=True, description="Detectar dominios desechables")
    check_policies: bool = Field(default=True, description="Validar contra políticas del sistema")
    
    class Config:
        schema_extra = {
            "example": {
                "to": ["user@example.com", "admin@company.com"],
                "subject": "Test subject with ñ special chars",
                "content": "Test content for validation",
                "check_format": True,
                "check_deliverability": False,
                "check_mx": True,
                "check_disposable": True,
                "check_policies": True
            }
        }


class ValidationTestResponse(BaseModel):
    """
    Respuesta del test de validación
    """
    overall_valid: bool = Field(..., description="Si toda la validación pasó")
    
    # Resultados por email
    email_results: List[Dict[str, Any]] = Field(..., description="Resultados de validación por email")
    
    # Validación de contenido
    content_validation: Optional[Dict[str, Any]] = Field(default=None, description="Validación del contenido")
    
    # Validación de políticas
    policy_validation: Optional[Dict[str, Any]] = Field(default=None, description="Validación contra políticas")
    
    # Estadísticas
    total_emails: int = Field(..., description="Total de emails validados")
    valid_emails: int = Field(..., description="Emails válidos")
    invalid_emails: int = Field(..., description="Emails inválidos")
    warnings_count: int = Field(default=0, description="Número de advertencias")
    
    # Metadata
    validation_time: Optional[float] = Field(default=None, description="Tiempo de validación en segundos")
    validated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp de la validación")
    
    class Config:
        schema_extra = {
            "example": {
                "overall_valid": True,
                "email_results": [
                    {
                        "email": "user@example.com",
                        "valid": True,
                        "checks": {
                            "format": True,
                            "mx_exists": True,
                            "disposable": False
                        },
                        "warnings": []
                    },
                    {
                        "email": "admin@company.com",
                        "valid": True,
                        "checks": {
                            "format": True,
                            "mx_exists": True,
                            "disposable": False
                        },
                        "warnings": ["Role-based email detected"]
                    }
                ],
                "content_validation": {
                    "subject": {"valid": True},
                    "content": {"valid": True}
                },
                "policy_validation": {
                    "whitelist": {"passed": True},
                    "limits": {"passed": True}
                },
                "total_emails": 2,
                "valid_emails": 2,
                "invalid_emails": 0,
                "warnings_count": 1,
                "validation_time": 0.234,
                "validated_at": "2024-01-15T10:30:00Z"
            }
        }