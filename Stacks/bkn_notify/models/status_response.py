"""
Pydantic models for status and logging responses
Esquemas para consulta de estado y logs de notificaciones
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """
    Estados posibles de una tarea de notificación
    """
    PENDING = "pending"           # En cola, no procesada aún
    PROCESSING = "processing"     # Siendo procesada por worker
    SUCCESS = "success"           # Enviada exitosamente
    FAILED = "failed"            # Falló el envío
    RETRY = "retry"              # En proceso de reintento
    CANCELLED = "cancelled"       # Cancelada manualmente


class LogLevel(str, Enum):
    """
    Niveles de log disponibles
    """
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorInfo(BaseModel):
    """
    Información detallada de errores
    """
    error_type: str = Field(..., description="Tipo de error (clase de excepción)")
    error_message: str = Field(..., description="Mensaje de error detallado")
    error_code: Optional[str] = Field(default=None, description="Código de error específico del proveedor")
    retry_after: Optional[int] = Field(default=None, description="Segundos hasta el próximo reintento")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error_type": "SMTPAuthenticationError",
                "error_message": "Invalid credentials for SMTP server",
                "error_code": "535",
                "retry_after": 300
            }
        }
    }


class ProviderInfo(BaseModel):
    """
    Información del proveedor utilizado
    """
    provider_name: str = Field(..., description="Nombre del proveedor")
    provider_type: str = Field(..., description="Tipo: smtp, api_sendgrid, api_ses, etc.")
    endpoint: Optional[str] = Field(default=None, description="Endpoint o servidor utilizado")
    response_time: Optional[float] = Field(default=None, description="Tiempo de respuesta en segundos")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "provider_name": "smtp_primary",
                "provider_type": "smtp",
                "endpoint": "smtp.gmail.com:587",
                "response_time": 1.234
            }
        }
    }


class DeliveryResult(BaseModel):
    """
    Resultado detallado de la entrega
    """
    delivered_at: Optional[datetime] = Field(default=None, description="Timestamp de entrega")
    provider_message_id: Optional[str] = Field(default=None, description="ID del mensaje del proveedor")
    delivery_status: Optional[str] = Field(default=None, description="Estado de entrega del proveedor")
    bounce_info: Optional[Dict[str, Any]] = Field(default=None, description="Información de rebote si aplica")
    open_tracking: Optional[Dict[str, Any]] = Field(default=None, description="Info de tracking de apertura")
    click_tracking: Optional[Dict[str, Any]] = Field(default=None, description="Info de tracking de clicks")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "delivered_at": "2024-01-15T10:35:22Z",
                "provider_message_id": "0000014a-f4d6-4f88-b8ca-6c2e4b8b4b4b",
                "delivery_status": "delivered",
                "bounce_info": None,
                "open_tracking": {"enabled": False},
                "click_tracking": {"enabled": False}
            }
        }
    }


class StatusResponse(BaseModel):
    """
    Respuesta completa del estado de una notificación
    """
    message_id: str = Field(..., description="ID único del mensaje")
    status: TaskStatus = Field(..., description="Estado actual de la tarea")
    celery_task_id: str = Field(..., description="ID de la tarea Celery")
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, description="Momento de creación")
    updated_at: Optional[datetime] = Field(default=None, description="Última actualización")
    started_at: Optional[datetime] = Field(default=None, description="Inicio de procesamiento")
    completed_at: Optional[datetime] = Field(default=None, description="Finalización (éxito o fallo)")
    
    # Información del envío
    provider: Optional[str] = Field(default=None, description="Proveedor utilizado")
    provider_info: Optional[ProviderInfo] = Field(default=None, description="Detalles del proveedor")
    recipients_count: Optional[int] = Field(default=None, description="Número de destinatarios")
    
    # Manejo de reintentos
    retry_count: Optional[int] = Field(default=0, description="Número de reintentos realizados")
    max_retries: Optional[int] = Field(default=3, description="Máximo de reintentos permitidos")
    next_retry_at: Optional[datetime] = Field(default=None, description="Próximo reintento programado")
    
    # Resultados
    result: Optional[DeliveryResult] = Field(default=None, description="Resultado de entrega exitosa")
    error: Optional[ErrorInfo] = Field(default=None, description="Información de error si aplica")
    
    # Métricas
    processing_duration: Optional[float] = Field(default=None, description="Duración del procesamiento en segundos")
    total_duration: Optional[float] = Field(default=None, description="Duración total desde creación")
    
    model_config = {
        "use_enum_values": True,
        "json_schema_extra": {
            "example": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "success",
                "celery_task_id": "b64c73fc-6b25-42b2-aa52-512c7a3b7cc8",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:35:22Z",
                "started_at": "2024-01-15T10:30:05Z",
                "completed_at": "2024-01-15T10:35:22Z",
                "provider": "smtp_primary",
                "provider_info": {
                    "provider_name": "smtp_primary",
                    "provider_type": "smtp",
                    "endpoint": "smtp.gmail.com:587",
                    "response_time": 1.234
                },
                "recipients_count": 3,
                "retry_count": 0,
                "max_retries": 3,
                "result": {
                    "delivered_at": "2024-01-15T10:35:22Z",
                    "provider_message_id": "0000014a-f4d6-4f88-b8ca-6c2e4b8b4b4b",
                    "delivery_status": "delivered"
                },
                "processing_duration": 17.5,
                "total_duration": 322.0
            }
        }
    }


class LogEntry(BaseModel):
    """
    Entrada individual de log
    """
    timestamp: datetime = Field(..., description="Timestamp del evento")
    level: LogLevel = Field(..., description="Nivel de log")
    event: str = Field(..., description="Tipo de evento")
    message: str = Field(..., description="Mensaje descriptivo del evento")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Detalles adicionales del evento")
    
    # Contexto
    celery_task_id: Optional[str] = Field(default=None, description="ID de tarea Celery si aplica")
    request_id: Optional[str] = Field(default=None, description="ID de request HTTP si aplica")
    
    @field_validator('message')
    @classmethod
    def validate_message_length(cls, v):
        """Valida longitud del mensaje"""
        if len(v) > 1000:
            return v[:997] + "..."
        return v
    
    model_config = {
        "use_enum_values": True,
        "json_schema_extra": {
            "example": {
                "timestamp": "2024-01-15T10:30:05Z",
                "level": "INFO",
                "event": "task_started",
                "message": "Email delivery task started",
                "details": {
                    "recipients_count": 3,
                    "provider": "smtp_primary",
                    "has_template": True
                },
                "celery_task_id": "b64c73fc-6b25-42b2-aa52-512c7a3b7cc8",
                "request_id": "req_550e8400-e29b-41d4-a716-446655440000"
            }
        }
    }


class LogsResponse(BaseModel):
    """
    Respuesta con logs paginados de una notificación
    """
    message_id: str = Field(..., description="ID del mensaje consultado")
    total_logs: int = Field(..., description="Número total de logs disponibles")
    logs: List[LogEntry] = Field(..., description="Entradas de log para la página actual")
    has_more: bool = Field(..., description="Si hay más logs disponibles")
    
    # Información de paginación
    limit: Optional[int] = Field(default=50, description="Límite de logs por página")
    offset: Optional[int] = Field(default=0, description="Offset de la consulta")
    
    # Metadata
    retrieved_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Timestamp de la consulta")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "total_logs": 8,
                "logs": [
                    {
                        "timestamp": "2024-01-15T10:35:22Z",
                        "level": "INFO",
                        "event": "email_sent",
                        "message": "Email sent successfully",
                        "details": {
                            "provider_response": {"status": "delivered"},
                            "delivery_time_seconds": 17.5
                        }
                    },
                    {
                        "timestamp": "2024-01-15T10:30:05Z",
                        "level": "INFO",
                        "event": "task_started",
                        "message": "Email delivery task started",
                        "details": {
                            "recipients_count": 3,
                            "provider": "smtp_primary"
                        }
                    }
                ],
                "has_more": False,
                "limit": 50,
                "offset": 0,
                "retrieved_at": "2024-01-15T11:00:00Z"
            }
        }
    }


class BatchStatusResponse(BaseModel):
    """
    Estado de un lote de notificaciones (bulk)
    """
    batch_id: str = Field(..., description="ID del lote")
    status: str = Field(..., description="Estado general del lote")
    total_messages: int = Field(..., description="Total de mensajes en el lote")
    
    # Contadores por estado
    pending_count: int = Field(default=0, description="Mensajes pendientes")
    processing_count: int = Field(default=0, description="Mensajes en procesamiento")
    success_count: int = Field(default=0, description="Mensajes enviados exitosamente")
    failed_count: int = Field(default=0, description="Mensajes fallidos")
    retry_count: int = Field(default=0, description="Mensajes en reintento")
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, description="Creación del lote")
    started_at: Optional[datetime] = Field(default=None, description="Inicio de procesamiento")
    completed_at: Optional[datetime] = Field(default=None, description="Finalización del lote")
    
    # Progreso
    progress_percentage: Optional[float] = Field(default=0.0, description="Porcentaje de progreso (0-100)")
    estimated_completion: Optional[datetime] = Field(default=None, description="Finalización estimada")
    
    # Estadísticas
    average_processing_time: Optional[float] = Field(default=None, description="Tiempo promedio de procesamiento")
    throughput_per_minute: Optional[float] = Field(default=None, description="Mensajes procesados por minuto")
    
    @field_validator('progress_percentage')
    @classmethod
    def validate_progress(cls, v):
        """Valida que el progreso esté entre 0 y 100"""
        if v < 0:
            return 0.0
        elif v > 100:
            return 100.0
        return round(v, 2)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "batch_id": "batch_550e8400-e29b-41d4-a716-446655440000",
                "status": "processing",
                "total_messages": 1000,
                "pending_count": 200,
                "processing_count": 50,
                "success_count": 720,
                "failed_count": 25,
                "retry_count": 5,
                "created_at": "2024-01-15T10:00:00Z",
                "started_at": "2024-01-15T10:01:00Z",
                "progress_percentage": 75.0,
                "estimated_completion": "2024-01-15T10:45:00Z",
                "average_processing_time": 2.3,
                "throughput_per_minute": 45.5
            }
        }
    }


class MetricsResponse(BaseModel):
    """
    Métricas generales del sistema de notificaciones
    """
    timeframe: str = Field(..., description="Marco temporal de las métricas")
    
    # Contadores generales
    total_messages: int = Field(default=0, description="Total de mensajes en el período")
    successful_deliveries: int = Field(default=0, description="Entregas exitosas")
    failed_deliveries: int = Field(default=0, description="Entregas fallidas")
    bounced_messages: int = Field(default=0, description="Mensajes rebotados")
    
    # Tasas de éxito
    success_rate: float = Field(default=0.0, description="Tasa de éxito (0-100)")
    bounce_rate: float = Field(default=0.0, description="Tasa de rebote (0-100)")
    
    # Performance
    average_delivery_time: Optional[float] = Field(default=None, description="Tiempo promedio de entrega")
    p95_delivery_time: Optional[float] = Field(default=None, description="Percentil 95 de tiempo de entrega")
    
    # Por proveedor
    provider_stats: Optional[Dict[str, Dict[str, Any]]] = Field(default=None, description="Estadísticas por proveedor")
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp de generación")
    
    @field_validator('success_rate', 'bounce_rate')
    @classmethod
    def validate_rates(cls, v):
        """Valida que las tasas estén entre 0 y 100"""
        if v < 0:
            return 0.0
        elif v > 100:
            return 100.0
        return round(v, 2)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "timeframe": "last_24_hours",
                "total_messages": 15420,
                "successful_deliveries": 14891,
                "failed_deliveries": 529,
                "bounced_messages": 156,
                "success_rate": 96.57,
                "bounce_rate": 1.01,
                "average_delivery_time": 2.34,
                "p95_delivery_time": 8.91,
                "provider_stats": {
                    "smtp_primary": {
                        "messages": 12000,
                        "success_rate": 97.2,
                        "avg_time": 2.1
                    },
                    "api_sendgrid": {
                        "messages": 3420,
                        "success_rate": 94.8,
                        "avg_time": 3.2
                    }
                },
                "generated_at": "2024-01-15T11:00:00Z"
            }
        }
    }