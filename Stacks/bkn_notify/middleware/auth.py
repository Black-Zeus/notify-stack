"""
Authentication middleware
Maneja autenticación por API key para endpoints protegidos
"""

import uuid
import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from app.constants import API_KEYS, AUTH_HEADER, REQUEST_ID_HEADER, HTTP_401_UNAUTHORIZED


async def auth_middleware(request: Request, call_next):
    """
    Middleware de autenticación por API key
    
    - Verifica X-API-Key en headers
    - Genera request_id único
    - Permite endpoints públicos (health, docs)
    - Bloquea endpoints protegidos sin API key válida
    """
    
    # Generar request ID único para tracking
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Agregar request ID a headers de respuesta
    def add_request_id_header(response):
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    
    # Rutas públicas que no requieren autenticación
    public_paths = [
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/healthz",
        "/api/readyz"
    ]
    
    # Verificar si es una ruta pública
    if request.url.path in public_paths:
        response = await call_next(request)
        return add_request_id_header(response)
    
    # Verificar si hay API keys configuradas
    if not API_KEYS or not any(key.strip() for key in API_KEYS):
        logging.warning("No API keys configured - allowing all requests")
        response = await call_next(request)
        return add_request_id_header(response)
    
    # Obtener API key del header
    api_key = request.headers.get(AUTH_HEADER)
    
    if not api_key:
        logging.warning(f"Missing API key for {request.url.path}", extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "client_ip": get_client_ip(request)
        })
        
        return JSONResponse(
            status_code=HTTP_401_UNAUTHORIZED,
            content={
                "error": "missing_api_key",
                "message": f"API key required in {AUTH_HEADER} header",
                "request_id": request_id
            },
            headers={REQUEST_ID_HEADER: request_id}
        )
    
    # Validar API key
    if api_key not in API_KEYS:
        logging.warning(f"Invalid API key for {request.url.path}", extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "client_ip": get_client_ip(request),
            "api_key_prefix": api_key[:8] + "..." if len(api_key) > 8 else api_key
        })
        
        return JSONResponse(
            status_code=HTTP_401_UNAUTHORIZED,
            content={
                "error": "invalid_api_key",
                "message": "Invalid API key provided",
                "request_id": request_id
            },
            headers={REQUEST_ID_HEADER: request_id}
        )
    
    # API key válida - agregar info al request state
    request.state.authenticated = True
    request.state.api_key = api_key
    
    # Log de acceso exitoso
    logging.debug(f"Authenticated request to {request.url.path}", extra={
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
        "client_ip": get_client_ip(request),
        "authenticated": True
    })
    
    # Continuar con la request
    response = await call_next(request)
    return add_request_id_header(response)


def get_client_ip(request: Request) -> str:
    """
    Obtiene IP del cliente considerando proxies
    """
    # Verificar headers de proxy comunes
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Tomar la primera IP (cliente original)
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback a IP directa
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return "unknown"


def validate_api_key(api_key: str) -> bool:
    """
    Valida formato y existencia de API key
    """
    if not api_key or not isinstance(api_key, str):
        return False
    
    # Verificar formato básico (mínimo 16 caracteres)
    if len(api_key.strip()) < 16:
        return False
    
    # Verificar contra lista de keys configuradas
    return api_key in API_KEYS


def get_authentication_info() -> dict:
    """
    Obtiene información sobre configuración de autenticación
    """
    return {
        "auth_enabled": bool(API_KEYS and any(key.strip() for key in API_KEYS)),
        "api_keys_count": len([key for key in API_KEYS if key.strip()]) if API_KEYS else 0,
        "auth_header": AUTH_HEADER,
        "public_paths": [
            "/",
            "/docs", 
            "/openapi.json",
            "/redoc",
            "/api/healthz",
            "/api/readyz"
        ]
    }


async def extract_request_info(request: Request) -> dict:
    """
    Extrae información útil del request para logging
    """
    return {
        "request_id": getattr(request.state, "request_id", None),
        "method": request.method,
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "client_ip": get_client_ip(request),
        "user_agent": request.headers.get("User-Agent", ""),
        "authenticated": getattr(request.state, "authenticated", False),
        "content_type": request.headers.get("Content-Type", ""),
        "content_length": request.headers.get("Content-Length", 0)
    }