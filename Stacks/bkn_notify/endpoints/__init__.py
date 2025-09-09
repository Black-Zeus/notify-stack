"""
Endpoints del sistema Notify API
Routers organizados por funcionalidad
"""

from .health import router as health_router
from .notify import router as notify_router  
from .status import router as status_router
from .test import router as test_router

__all__ = [
    "health_router",
    "notify_router", 
    "status_router",
    "test_router"
]