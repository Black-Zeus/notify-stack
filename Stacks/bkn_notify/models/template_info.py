"""
Template Info Models - Modelos para endpoints de información de templates
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TemplateInfo(BaseModel):
    """
    Información básica de un template para listados
    """
    template_id: str = Field(..., description="ID del template (nombre.version)")
    name: str = Field(..., description="Nombre descriptivo del template")
    description: str = Field(..., description="Descripción del propósito del template")
    category: str = Field(default="general", description="Categoría del template")
    versions: List[str] = Field(default_factory=list, description="Versiones disponibles")
    latest_version: str = Field(..., description="Versión más reciente")
    required_vars: List[str] = Field(default_factory=list, description="Variables requeridas")
    optional_sections: List[str] = Field(default_factory=list, description="Secciones condicionales")
    created_at: str = Field(..., description="Fecha de creación")

    model_config = {
        "json_schema_extra": {
            "example": {
                "template_id": "welcome-alert.v1",
                "name": "Mensaje de Bienvenida",
                "description": "Template para dar la bienvenida a nuevos usuarios",
                "category": "user-management",
                "versions": ["v1"],
                "latest_version": "v1",
                "required_vars": ["user_name", "company_name", "user_email"],
                "optional_sections": ["activation_link"],
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class TemplateListResponse(BaseModel):
    """
    Respuesta del endpoint de listado de templates
    """
    templates: List[TemplateInfo] = Field(..., description="Lista de templates disponibles")
    total_count: int = Field(..., description="Total de templates encontrados")
    categories: List[str] = Field(default_factory=list, description="Categorías disponibles")
    retrieved_at: str = Field(..., description="Timestamp de cuando se obtuvo la información")

    model_config = {
        "json_schema_extra": {
            "example": {
                "templates": [
                    {
                        "template_id": "alerta-simple.v1",
                        "name": "Alerta Simple",
                        "description": "Template básico para alertas del sistema",
                        "category": "alerts",
                        "versions": ["v1"],
                        "latest_version": "v1",
                        "required_vars": ["host", "estado", "hora"],
                        "optional_sections": [],
                        "created_at": "2024-01-15T10:30:00Z"
                    },
                    {
                        "template_id": "welcome-alert.v1",
                        "name": "Mensaje de Bienvenida",
                        "description": "Template para dar la bienvenida a nuevos usuarios",
                        "category": "user-management",
                        "versions": ["v1"],
                        "latest_version": "v1",
                        "required_vars": ["user_name", "company_name", "user_email"],
                        "optional_sections": ["activation_link"],
                        "created_at": "2024-01-15T11:00:00Z"
                    }
                ],
                "total_count": 2,
                "categories": ["alerts", "user-management"],
                "retrieved_at": "2024-01-15T14:30:00Z"
            }
        }
    }


class TemplateFileInfo(BaseModel):
    """
    Información detallada de un archivo del template
    """
    size_bytes: Optional[int] = Field(None, description="Tamaño del archivo en bytes")
    line_count: Optional[int] = Field(None, description="Número de líneas")
    variables_used: List[str] = Field(default_factory=list, description="Variables encontradas en el archivo")
    conditionals_used: List[str] = Field(default_factory=list, description="Condicionales encontrados en el archivo")
    last_modified: Optional[str] = Field(None, description="Fecha de última modificación")
    status: Optional[str] = Field(None, description="Estado del archivo (missing, error, etc.)")
    error: Optional[str] = Field(None, description="Error al procesar el archivo")

    model_config = {
        "json_schema_extra": {
            "example": {
                "size_bytes": 1024,
                "line_count": 25,
                "variables_used": ["user_name", "company_name", "activation_link"],
                "conditionals_used": ["activation_link"],
                "last_modified": "2024-01-15T10:30:00Z"
            }
        }
    }


class TemplateStatistics(BaseModel):
    """
    Estadísticas del template
    """
    total_files: int = Field(..., description="Total de archivos en el template")
    total_size_bytes: int = Field(..., description="Tamaño total en bytes")
    has_all_required_files: bool = Field(..., description="Si tiene todos los archivos requeridos")

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_files": 4,
                "total_size_bytes": 8192,
                "has_all_required_files": True
            }
        }
    }


class TemplateDetailResponse(BaseModel):
    """
    Respuesta detallada de información de un template específico
    """
    template_id: str = Field(..., description="ID del template")
    name: str = Field(..., description="Nombre descriptivo")
    description: str = Field(..., description="Descripción del propósito")
    category: str = Field(default="general", description="Categoría")
    version: str = Field(..., description="Versión actual")
    required_variables: List[str] = Field(default_factory=list, description="Variables obligatorias")
    conditional_sections: List[str] = Field(default_factory=list, description="Secciones condicionales")
    example_usage: Dict[str, Any] = Field(default_factory=dict, description="Ejemplo de uso con variables")
    files_info: Dict[str, TemplateFileInfo] = Field(default_factory=dict, description="Información de archivos")
    statistics: TemplateStatistics = Field(..., description="Estadísticas del template")
    last_modified: str = Field(..., description="Fecha de última modificación")
    created_at: str = Field(..., description="Fecha de creación")

    model_config = {
        "json_schema_extra": {
            "example": {
                "template_id": "welcome-alert.v1",
                "name": "Mensaje de Bienvenida",
                "description": "Template para dar la bienvenida a nuevos usuarios",
                "category": "user-management",
                "version": "v1",
                "required_variables": ["user_name", "company_name", "user_email"],
                "conditional_sections": ["activation_link"],
                "example_usage": {
                    "user_name": "Juan Pérez",
                    "company_name": "Empresa Tecnológica S.A.",
                    "user_email": "juan.perez@empresa.com",
                    "activation_link": "https://app.empresa.com/activate/abc123xyz"
                },
                "files_info": {
                    "subject.txt": {
                        "size_bytes": 45,
                        "line_count": 1,
                        "variables_used": ["company_name"],
                        "conditionals_used": [],
                        "last_modified": "2024-01-15T10:30:00Z"
                    },
                    "body.txt": {
                        "size_bytes": 512,
                        "line_count": 18,
                        "variables_used": ["user_name", "company_name", "user_email", "activation_link"],
                        "conditionals_used": ["activation_link"],
                        "last_modified": "2024-01-15T10:30:00Z"
                    },
                    "body.html": {
                        "size_bytes": 4096,
                        "line_count": 120,
                        "variables_used": ["user_name", "company_name", "user_email", "activation_link", "timestamp"],
                        "conditionals_used": ["activation_link"],
                        "last_modified": "2024-01-15T10:30:00Z"
                    },
                    "variables.yml": {
                        "size_bytes": 256,
                        "line_count": 15,
                        "variables_used": [],
                        "conditionals_used": [],
                        "last_modified": "2024-01-15T10:30:00Z"
                    }
                },
                "statistics": {
                    "total_files": 4,
                    "total_size_bytes": 4909,
                    "has_all_required_files": True
                },
                "last_modified": "2024-01-15T10:30:00Z",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class TemplateValidationResponse(BaseModel):
    """
    Respuesta de validación de variables para un template
    """
    template_id: str = Field(..., description="ID del template validado")
    is_valid: bool = Field(..., description="Si las variables proporcionadas son válidas")
    missing_required: List[str] = Field(default_factory=list, description="Variables requeridas faltantes")
    unknown_variables: List[str] = Field(default_factory=list, description="Variables no reconocidas")
    missing_conditionals: List[str] = Field(default_factory=list, description="Condicionales requeridos faltantes")
    suggestions: List[str] = Field(default_factory=list, description="Sugerencias para corregir la validación")
    validated_at: str = Field(..., description="Timestamp de validación")

    model_config = {
        "json_schema_extra": {
            "example": {
                "template_id": "welcome-alert.v1",
                "is_valid": False,
                "missing_required": ["company_name"],
                "unknown_variables": ["invalid_var"],
                "missing_conditionals": [],
                "suggestions": [
                    "Add required variable 'company_name'",
                    "Remove unknown variable 'invalid_var'",
                    "Consider adding 'activation_link' for complete user onboarding"
                ],
                "validated_at": "2024-01-15T14:30:00Z"
            }
        }
    }