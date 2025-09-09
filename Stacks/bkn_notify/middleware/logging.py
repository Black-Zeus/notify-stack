"""
Logging middleware and setup
Configuración de logging estructurado JSON para el sistema
"""

import logging
import logging.config
import json
import sys
from datetime import datetime
from typing import Dict, Any

from constants import LOG_LEVEL, LOG_FORMAT, SERVICE_NAME


def setup_logging():
    """
    Configura logging estructurado para el sistema
    """
    
    # Configuración de logging según formato especificado
    if LOG_FORMAT.lower() == "json":
        setup_json_logging()
    else:
        setup_standard_logging()
    
    # Configurar nivel de logging
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)
    
    # Suprimir logs verbosos de librerías externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    
    logging.info(f"Logging configured: format={LOG_FORMAT}, level={LOG_LEVEL}")


def setup_json_logging():
    """
    Configura logging estructurado JSON
    """
    
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JsonFormatter,
            },
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": LOG_LEVEL,
                "formatter": "json",
                "stream": sys.stdout
            }
        },
        "root": {
            "level": LOG_LEVEL,
            "handlers": ["console"]
        },
        "loggers": {
            SERVICE_NAME: {
                "level": LOG_LEVEL,
                "handlers": ["console"],
                "propagate": False
            }
        }
    }
    
    logging.config.dictConfig(logging_config)


def setup_standard_logging():
    """
    Configura logging estándar (no JSON)
    """
    
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": LOG_LEVEL,
                "formatter": "standard",
                "stream": sys.stdout
            }
        },
        "root": {
            "level": LOG_LEVEL,
            "handlers": ["console"]
        }
    }
    
    logging.config.dictConfig(logging_config)


class JsonFormatter(logging.Formatter):
    """
    Formatter personalizado para logging JSON estructurado
    """
    
    def format(self, record):
        """
        Formatea log record como JSON estructurado
        """
        
        # Información base del log
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": SERVICE_NAME
        }
        
        # Agregar información adicional si está disponible
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
            
        if hasattr(record, "message_id"):
            log_entry["message_id"] = record.message_id
            
        if hasattr(record, "celery_task_id"):
            log_entry["celery_task_id"] = record.celery_task_id
            
        if hasattr(record, "event"):
            log_entry["event"] = record.event
        
        # Agregar información del módulo/función
        log_entry["module"] = record.module
        log_entry["function"] = record.funcName
        log_entry["line"] = record.lineno
        
        # Agregar información de excepción si existe
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Agregar campos extras del record
        extras = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 'exc_text', 
                          'stack_info', 'request_id', 'message_id', 'celery_task_id', 'event']:
                try:
                    # Solo agregar valores serializables
                    json.dumps(value)
                    extras[key] = value
                except (TypeError, ValueError):
                    extras[key] = str(value)
        
        if extras:
            log_entry["extras"] = extras
        
        return json.dumps(log_entry, ensure_ascii=False)


class RequestLoggingMiddleware:
    """
    Middleware para logging automático de requests HTTP
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = datetime.utcnow()
        
        # Wrapper para capturar respuesta
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Log de request completado
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                # Extraer información del scope
                method = scope.get("method", "")
                path = scope.get("path", "")
                status_code = message.get("status", 0)
                
                # Log estructurado de la request
                logging.info(
                    f"{method} {path} - {status_code}",
                    extra={
                        "http_method": method,
                        "http_path": path,
                        "http_status": status_code,
                        "duration_seconds": duration,
                        "client_ip": get_client_ip_from_scope(scope)
                    }
                )
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)


def get_client_ip_from_scope(scope: Dict[str, Any]) -> str:
    """
    Extrae IP del cliente desde scope ASGI
    """
    headers = dict(scope.get("headers", []))
    
    # Verificar X-Forwarded-For
    forwarded_for = headers.get(b"x-forwarded-for")
    if forwarded_for:
        return forwarded_for.decode().split(",")[0].strip()
    
    # Verificar X-Real-IP
    real_ip = headers.get(b"x-real-ip")
    if real_ip:
        return real_ip.decode().strip()
    
    # IP directa del cliente
    client_info = scope.get("client")
    if client_info:
        return client_info[0]
    
    return "unknown"


def log_structured(
    level: str,
    message: str,
    event: str = None,
    request_id: str = None,
    message_id: str = None,
    **kwargs
):
    """
    Utility function para logging estructurado
    """
    
    extra_data = {
        "event": event,
        "request_id": request_id,
        "message_id": message_id,
        **kwargs
    }
    
    # Remover valores None
    extra_data = {k: v for k, v in extra_data.items() if v is not None}
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.log(log_level, message, extra=extra_data)


def get_logging_config() -> Dict[str, Any]:
    """
    Obtiene configuración actual de logging
    """
    return {
        "service": SERVICE_NAME,
        "log_level": LOG_LEVEL,
        "log_format": LOG_FORMAT,
        "json_logging": LOG_FORMAT.lower() == "json",
        "handlers": list(logging.getLogger().handlers),
        "loggers": list(logging.Logger.manager.loggerDict.keys())
    }


# Logger específico para el servicio
logger = logging.getLogger(SERVICE_NAME)