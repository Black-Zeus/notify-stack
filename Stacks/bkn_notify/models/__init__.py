"""
Models package
Exporta todos los modelos Pydantic del sistema de notificaciones
"""

# Modelos de request/response para notificaciones
from .notify_request import (
    AttachmentModel,
    NotifyRequest,
    NotifyResponse,
    BulkNotifyRequest,
    BulkNotifyResponse
)

# Modelos de estado y logs
from .status_response import (
    TaskStatus,
    LogLevel,
    ErrorInfo,
    ProviderInfo,
    DeliveryResult,
    StatusResponse,
    LogEntry,
    LogsResponse,
    BatchStatusResponse,
    MetricsResponse
)

# Modelos de información de templates
from .template_info import (
    TemplateInfo,
    TemplateListResponse,
    TemplateValidationResponse
)

# Exports organizados por categoría
__all__ = [
    # === NOTIFICATION MODELS ===
    "AttachmentModel",
    "NotifyRequest", 
    "NotifyResponse",
    "BulkNotifyRequest",
    "BulkNotifyResponse",
    
    # === STATUS & LOGGING MODELS ===
    "TaskStatus",
    "LogLevel", 
    "ErrorInfo",
    "ProviderInfo",
    "DeliveryResult",
    "StatusResponse",
    "LogEntry",
    "LogsResponse",
    "BatchStatusResponse", 
    "MetricsResponse",
    
    # === TEMPLATE MODELS ===
    "TemplateInfo",
    "TemplateListResponse",
    "TemplateValidationResponse"
]

# Información del paquete de modelos
MODEL_INFO = {
    "package": "models",
    "description": "Pydantic models for Notify API system",
    "categories": {
        "notifications": [
            "AttachmentModel", "NotifyRequest", "NotifyResponse", 
            "BulkNotifyRequest", "BulkNotifyResponse"
        ],
        "status_logging": [
            "TaskStatus", "LogLevel", "ErrorInfo", "ProviderInfo", 
            "DeliveryResult", "StatusResponse", "LogEntry", "LogsResponse",
            "BatchStatusResponse", "MetricsResponse"
        ],
        "templates": [
            "TemplateInfo", "TemplateListResponse", "TemplateValidationResponse"
        ]
    },
    "total_models": len(__all__),
    "features": [
        "pydantic_v2_compatible",
        "json_schema_generation", 
        "fastapi_integration",
        "input_validation",
        "serialization",
        "documentation_examples"
    ]
}


def get_model_by_name(model_name: str):
    """
    Obtiene modelo por nombre string
    
    Args:
        model_name: Nombre del modelo (ej: "NotifyRequest")
        
    Returns:
        Clase del modelo Pydantic o None si no existe
    """
    import sys
    current_module = sys.modules[__name__]
    return getattr(current_module, model_name, None)


def get_models_by_category(category: str) -> list:
    """
    Obtiene modelos por categoría
    
    Args:
        category: notifications, status_logging, templates
        
    Returns:
        Lista de clases de modelos en esa categoría
    """
    category_models = MODEL_INFO["categories"].get(category, [])
    return [get_model_by_name(name) for name in category_models]


def validate_all_models():
    """
    Valida que todos los modelos se puedan importar correctamente
    
    Returns:
        Dict con resultado de validación
    """
    validation_result = {
        "valid": True,
        "errors": [],
        "models_checked": 0,
        "models_valid": 0
    }
    
    for model_name in __all__:
        validation_result["models_checked"] += 1
        
        try:
            model_class = get_model_by_name(model_name)
            if model_class is None:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Model {model_name} not found")
            else:
                # Verificar que es un modelo Pydantic válido
                if hasattr(model_class, '__fields__') or hasattr(model_class, 'model_fields'):
                    validation_result["models_valid"] += 1
                else:
                    validation_result["valid"] = False
                    validation_result["errors"].append(f"Model {model_name} is not a valid Pydantic model")
                    
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Error loading {model_name}: {str(e)}")
    
    return validation_result


# Validación automática al importar (solo en desarrollo)
import os
if os.getenv("VALIDATE_MODELS_ON_IMPORT", "false").lower() == "true":
    validation = validate_all_models()
    if not validation["valid"]:
        import logging
        logging.warning(f"Model validation issues: {validation['errors']}")