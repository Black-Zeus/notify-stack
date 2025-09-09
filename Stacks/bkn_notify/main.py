"""
Notify API - FastAPI Entry Point
Sistema de notificaciones por correo con Celery y Redis
"""

import os
import sys
import logging
from contextlib import asynccontextmanager

# Agregar directorio del proyecto al sys.path para imports absolutos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyHeader

# Imports directos con manejo de errores
try:
    import constants
except ImportError:
    class Constants:
        SERVICE_NAME = "notify-api"
        API_VERSION = "1.0.0"
        LOG_LEVEL = "INFO"
    constants = Constants()

# Definir esquema de seguridad para Swagger
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=getattr(logging, getattr(constants, 'LOG_LEVEL', 'INFO'), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logging.info(f"{constants.SERVICE_NAME} starting up")
    yield
    logging.info(f"{constants.SERVICE_NAME} shutting down")


# Crear app FastAPI con configuración de seguridad para Swagger
app = FastAPI(
    title="Notify API",
    description="Sistema ligero de notificaciones por correo",
    version=constants.API_VERSION,
    docs_url="/swagger",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    # Configuración de seguridad para Swagger UI
    swagger_ui_parameters={
        "persistAuthorization": True,
    }
)

# Configurar esquema de seguridad en OpenAPI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Agregar configuración de seguridad
    openapi_schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API Key requerida para acceder a los endpoints"
        }
    }
    
    # Aplicar seguridad a todos los endpoints excepto públicos
    for path, path_item in openapi_schema["paths"].items():
        # Endpoints públicos que no requieren autenticación
        if path in ["/", "/api/info", "/api/healthz", "/api/readyz"]:
            continue
            
        for method, operation in path_item.items():
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                operation["security"] = [{"APIKeyHeader": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Alias /docs → /swagger
@app.get("/docs", include_in_schema=False)
async def docs_alias():
    return RedirectResponse(url="/swagger", status_code=307)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Middleware de autenticación (opcional) con whitelist de docs
try:
    from middleware.auth import auth_middleware
    ALLOWED_PATHS = {"/swagger", "/docs", "/redoc", "/openapi.json"}

    async def _auth_wrapper(request: Request, call_next):
        if request.url.path in ALLOWED_PATHS:
            return await call_next(request)
        return await auth_middleware(request, call_next)

    app.middleware("http")(_auth_wrapper)
    logging.info("Authentication middleware loaded (with docs whitelist)")
except ImportError:
    logging.warning("Authentication middleware not available - API will be open")

# 🚀 Registrar routers (importaciones absolutas)
try:
    from endpoints.health import router as health_router
    from endpoints.notify import router as notify_router
    from endpoints.status import router as status_router
    from endpoints.test import router as test_router

    app.include_router(health_router, prefix="/api", tags=["Health"])
    app.include_router(notify_router, prefix="/api", tags=["Notifications"])
    app.include_router(status_router, prefix="/api", tags=["Status"])
    app.include_router(test_router, prefix="/api", tags=["Testing"])

    routers_loaded = ["health", "notify", "status", "test"]
except Exception as e:
    logging.error(f"Error cargando routers: {e}", exc_info=True)
    routers_loaded = []

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, "request_id", None),
        },
    )

@app.get("/")
async def root():
    return {
        "service": constants.SERVICE_NAME,
        "version": constants.API_VERSION,
        "status": "running",
        "swagger_ui": "/swagger",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "routers_loaded": routers_loaded,
    }

@app.get("/api/info")
async def api_info():
    return {
        "service": constants.SERVICE_NAME,
        "version": constants.API_VERSION,
        "routers_loaded": routers_loaded,
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "false").lower() == "true"
    # 👇 Mantener coherencia: ejecutar por módulo (main:app)
    uvicorn.run("main:app", host=host, port=port, reload=debug, log_config=None)