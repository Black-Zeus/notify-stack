"""
Notify API - Sistema de notificaciones por correo
Backend ligero con FastAPI, Celery y Redis
"""

__version__ = "1.0.0"
__author__ = "notify-stack"
__description__ = "Sistema ligero de notificaciones por correo"

# Exportar componentes principales para importación directa
from app.constants import (
    SERVICE_NAME,
    API_VERSION,
    TASK_STATES
)

__all__ = [
    "SERVICE_NAME", 
    "API_VERSION", 
    "TASK_STATES"
]