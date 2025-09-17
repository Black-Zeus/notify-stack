"""
Constants para el sistema Notify API
"""

import os

# Información del servicio
SERVICE_NAME = "notify-api"
API_VERSION = "1.0.0"

# Configuración de logging
LOG_FORMAT = "json"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://bkn_redis:6379/0")
REDIS_TTL_DEFAULT = int(os.getenv("REDIS_TTL_DEFAULT", "3600"))  # 1 hora
REDIS_TTL_IDEMPOTENCY = int(os.getenv("REDIS_TTL_IDEMPOTENCY", "86400"))  # 24 horas

# Celery
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# API Keys y autenticación
API_KEYS = os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else []
AUTH_HEADER = "X-API-Key"

# Límites de payload
MAX_PAYLOAD_SIZE = int(os.getenv("MAX_PAYLOAD_SIZE", "1048576"))  # 1MB
MAX_RECIPIENTS = int(os.getenv("MAX_RECIPIENTS", "100"))
MAX_ATTACHMENTS = int(os.getenv("MAX_ATTACHMENTS", "10"))
MAX_ATTACHMENT_SIZE = int(os.getenv("MAX_ATTACHMENT_SIZE", "5242880"))  # 5MB

# Paths de configuración
CONFIG_DIR = "/app/Config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.yml")
PROVIDERS_FILE = os.path.join(CONFIG_DIR, "providers.yml") 
POLICY_FILE = os.path.join(CONFIG_DIR, "policy.yml")
TEMPLATES_DIR = "/app/templates"
TEMPLATES_BASE_PATH = TEMPLATES_DIR

# Estados de tareas Celery
TASK_STATES = {
    "PENDING": "PENDING",
    "STARTED": "PROCESSING", 
    "SUCCESS": "SUCCESS",
    "FAILURE": "FAILED",
    "RETRY": "RETRY",
    "REVOKED": "CANCELLED"
}

# Códigos de respuesta HTTP
HTTP_200_OK = 200
HTTP_202_ACCEPTED = 202
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_404_NOT_FOUND = 404
HTTP_409_CONFLICT = 409
HTTP_422_UNPROCESSABLE_ENTITY = 422
HTTP_500_INTERNAL_SERVER_ERROR = 500
HTTP_503_SERVICE_UNAVAILABLE = 503

# Headers especiales
IDEMPOTENCY_HEADER = "Idempotency-Key"
REQUEST_ID_HEADER = "X-Request-ID"

# Prefijos Redis
REDIS_KEY_PREFIX = "notify:"
REDIS_IDEMPOTENCY_PREFIX = f"{REDIS_KEY_PREFIX}idem:"
REDIS_TASK_PREFIX = f"{REDIS_KEY_PREFIX}task:"
REDIS_LOG_PREFIX = f"{REDIS_KEY_PREFIX}log:"

# Timeouts
CELERY_TASK_TIMEOUT = int(os.getenv("CELERY_TASK_TIMEOUT", "300"))  # 5 minutos
SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "30"))  # 30 segundos

# Retry policy
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF = int(os.getenv("RETRY_BACKOFF", "2"))  # Exponential backoff factor

# Test endpoint
TEST_RECIPIENTS = ["test@example.com"]  # Recipients for test endpoint

# =============================================================================
# TWILIO CONSTANTS
# =============================================================================
# SMS limits
SMS_MAX_LENGTH = int(os.getenv("SMS_MAX_LENGTH", "1600"))  # SMS limit including concatenation

# WhatsApp limits  
WHATSAPP_MAX_LENGTH = int(os.getenv("WHATSAPP_MAX_LENGTH", "4096"))  # WhatsApp text message limit
WHATSAPP_MAX_MEDIA = int(os.getenv("WHATSAPP_MAX_MEDIA", "10"))  # Max media attachments per message

# Twilio timeouts
TWILIO_DEFAULT_TIMEOUT = int(os.getenv("TWILIO_TIMEOUT", "30"))  # 30 seconds

# =============================================================================
# NUEVAS CONSTANTES PARA SMS/WHATSAPP - AGREGADAS DE FORMA SEGURA
# =============================================================================

# Límites adicionales SMS/WhatsApp (conservadores para no romper nada)
MAX_SMS_RECIPIENTS = int(os.getenv("MAX_SMS_RECIPIENTS", "10"))  # Límite conservador
MAX_WHATSAPP_RECIPIENTS = int(os.getenv("MAX_WHATSAPP_RECIPIENTS", "10"))

# Credenciales Twilio (solo ENV vars, sin defaults para seguridad)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_SMS_FROM = os.getenv("TWILIO_SMS_FROM")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")

# Canales soportados (extensión segura)
SUPPORTED_CHANNELS = ["email", "sms", "whatsapp"]
DEFAULT_CHANNEL = "email"  # Mantiene comportamiento actual por defecto

# Estados adicionales para SMS/WhatsApp (sin cambiar TASK_STATES existente)
SMS_TWILIO_STATES = {
    "QUEUED": "QUEUED",
    "SENDING": "SENDING", 
    "SENT": "SENT",
    "DELIVERED": "DELIVERED",
    "UNDELIVERED": "UNDELIVERED"
}

# Headers adicionales para multi-canal
CHANNEL_HEADER = "X-Channel"  # Opcional, no rompe requests existentes

# Prefijos Redis adicionales (no cambian los existentes)
REDIS_SMS_PREFIX = f"{REDIS_KEY_PREFIX}sms:"
REDIS_WHATSAPP_PREFIX = f"{REDIS_KEY_PREFIX}whatsapp:"


# =============================================================================
# NUEVAS CONSTANTES PARA PROVIDERS - Agregar al archivo constants.py existente
# =============================================================================

# =============================================================================
# PROVIDER DATABASE CONFIGURATION
# =============================================================================

# Flag principal para habilitar/deshabilitar providers desde base de datos
USE_DATABASE_PROVIDERS = os.getenv("USE_DATABASE_PROVIDERS", "false").lower() == "true"

# Modo dual: fallback automático YAML -> DB en caso de error
PROVIDERS_DUAL_MODE = os.getenv("PROVIDERS_DUAL_MODE", "true").lower() == "true"

# Timeout para operaciones de providers en base de datos (segundos)
PROVIDERS_DB_TIMEOUT = int(os.getenv("PROVIDERS_DB_TIMEOUT", "5"))

# Ambiente de providers por defecto
PROVIDERS_DEFAULT_ENVIRONMENT = os.getenv("PROVIDERS_DEFAULT_ENVIRONMENT", "production")

# =============================================================================
# PROVIDERS CACHE CONFIGURATION
# =============================================================================

# TTL específicos para cache de providers (segundos)
REDIS_TTL_PROVIDERS = int(os.getenv("REDIS_TTL_PROVIDERS", "3600"))           # 1 hora
REDIS_TTL_PROVIDERS_CONFIG = int(os.getenv("REDIS_TTL_PROVIDERS_CONFIG", "1800"))  # 30 minutos  
REDIS_TTL_PROVIDERS_HEALTH = int(os.getenv("REDIS_TTL_PROVIDERS_HEALTH", "300"))   # 5 minutos
REDIS_TTL_PROVIDER_GROUPS = int(os.getenv("REDIS_TTL_PROVIDER_GROUPS", "7200"))    # 2 horas

# Prefijos de cache para providers
CACHE_PREFIX_PROVIDER = "provider:"
CACHE_PREFIX_PROVIDERS_LIST = "providers:"
CACHE_PREFIX_PROVIDER_CONFIG = "provider_config:"
CACHE_PREFIX_PROVIDER_HEALTH = "provider_health:"
CACHE_PREFIX_PROVIDER_GROUP = "provider_group:"
CACHE_PREFIX_GROUP_MEMBERS = "group_members:"

# Configuración de invalidación de cache
CACHE_INVALIDATION_BATCH_SIZE = int(os.getenv("CACHE_INVALIDATION_BATCH_SIZE", "50"))

# =============================================================================
# PROVIDERS PERFORMANCE LIMITS
# =============================================================================

# Límites de performance para carga de providers
PROVIDERS_MAX_LOAD_TIME_MS = int(os.getenv("PROVIDERS_MAX_LOAD_TIME_MS", "50"))
PROVIDERS_MAX_CACHE_SIZE_MB = int(os.getenv("PROVIDERS_MAX_CACHE_SIZE_MB", "10"))

# Límites de búsqueda y paginación
PROVIDERS_MAX_SEARCH_RESULTS = int(os.getenv("PROVIDERS_MAX_SEARCH_RESULTS", "100"))
PROVIDERS_DEFAULT_PAGE_SIZE = int(os.getenv("PROVIDERS_DEFAULT_PAGE_SIZE", "20"))

# =============================================================================
# PROVIDERS HEALTH CHECK CONFIGURATION
# =============================================================================

# Configuración por defecto de health checks
HEALTH_CHECK_DEFAULT_INTERVAL = int(os.getenv("HEALTH_CHECK_DEFAULT_INTERVAL", "5"))  # minutos
HEALTH_CHECK_DEFAULT_TIMEOUT = int(os.getenv("HEALTH_CHECK_DEFAULT_TIMEOUT", "30"))   # segundos
HEALTH_CHECK_DEFAULT_RETRIES = int(os.getenv("HEALTH_CHECK_DEFAULT_RETRIES", "3"))

# Thresholds de salud
HEALTH_CHECK_FAILURE_THRESHOLD = int(os.getenv("HEALTH_CHECK_FAILURE_THRESHOLD", "3"))
HEALTH_CHECK_SUCCESS_THRESHOLD = int(os.getenv("HEALTH_CHECK_SUCCESS_THRESHOLD", "2"))
HEALTH_CHECK_MAX_RESPONSE_TIME_MS = int(os.getenv("HEALTH_CHECK_MAX_RESPONSE_TIME_MS", "5000"))

# =============================================================================
# PROVIDERS ROUTING CONFIGURATION
# =============================================================================

# Configuración de routing de providers
ROUTING_DEFAULT_STRATEGY = os.getenv("ROUTING_DEFAULT_STRATEGY", "priority")
ROUTING_MAX_RETRIES_PER_GROUP = int(os.getenv("ROUTING_MAX_RETRIES_PER_GROUP", "3"))
ROUTING_FAILOVER_TIMEOUT = int(os.getenv("ROUTING_FAILOVER_TIMEOUT", "30"))  # segundos

# Load balancing
LOAD_BALANCE_ALGORITHMS = ["priority", "round_robin", "failover", "load_balance", "random"]
LOAD_BALANCE_DEFAULT_WEIGHT = int(os.getenv("LOAD_BALANCE_DEFAULT_WEIGHT", "10"))

# =============================================================================
# PROVIDERS VALIDATION RULES
# =============================================================================

# Límites de configuración de providers
PROVIDER_KEY_MAX_LENGTH = 50
PROVIDER_NAME_MAX_LENGTH = 100
PROVIDER_DESCRIPTION_MAX_LENGTH = 500
PROVIDER_CONFIG_MAX_SIZE_KB = int(os.getenv("PROVIDER_CONFIG_MAX_SIZE_KB", "64"))

# Tipos de proveedores permitidos
ALLOWED_PROVIDER_TYPES = ["smtp", "api", "webhook", "twilio"]

# Ambientes permitidos
ALLOWED_ENVIRONMENTS = ["development", "staging", "production"]

# =============================================================================
# PROVIDERS SECURITY CONFIGURATION
# =============================================================================

# Encriptación de credenciales (para implementación futura)
CREDENTIALS_ENCRYPTION_ENABLED = os.getenv("CREDENTIALS_ENCRYPTION_ENABLED", "false").lower() == "true"
CREDENTIALS_ENCRYPTION_KEY = os.getenv("CREDENTIALS_ENCRYPTION_KEY", "")

# Campos sensibles que deben ir en credentials_json
SENSITIVE_CREDENTIAL_FIELDS = {
    "password", "api_key", "secret_key", "auth_token", "private_key", 
    "client_secret", "smtp_password", "smtp_pass", "certificate"
}

# Headers que contienen información sensible
SENSITIVE_HEADER_PATTERNS = ["authorization", "x-api-key", "bearer", "token"]

# =============================================================================
# PROVIDERS MONITORING CONFIGURATION
# =============================================================================

# Configuración de métricas de providers
METRICS_PROVIDERS_ENABLED = os.getenv("METRICS_PROVIDERS_ENABLED", "true").lower() == "true"
METRICS_COLLECTION_INTERVAL = int(os.getenv("METRICS_COLLECTION_INTERVAL", "300"))  # 5 minutos

# Alertas de providers
ALERTS_PROVIDER_FAILURE_THRESHOLD = float(os.getenv("ALERTS_PROVIDER_FAILURE_THRESHOLD", "5.0"))  # %
ALERTS_PROVIDER_RESPONSE_TIME_THRESHOLD = int(os.getenv("ALERTS_PROVIDER_RESPONSE_TIME_THRESHOLD", "10000"))  # ms
ALERTS_WEBHOOK_URL = os.getenv("ALERTS_WEBHOOK_URL", "")

# =============================================================================
# PROVIDERS COST OPTIMIZATION
# =============================================================================

# Configuración de optimización de costos
COST_OPTIMIZATION_ENABLED = os.getenv("COST_OPTIMIZATION_ENABLED", "false").lower() == "true"
COST_TRACKING_CURRENCY = os.getenv("COST_TRACKING_CURRENCY", "USD")

# Límites de costo por defecto
DEFAULT_DAILY_COST_LIMIT = float(os.getenv("DEFAULT_DAILY_COST_LIMIT", "50.0"))
DEFAULT_COST_ALERT_THRESHOLD = float(os.getenv("DEFAULT_COST_ALERT_THRESHOLD", "30.0"))

# =============================================================================
# PROVIDERS MIGRATION CONFIGURATION
# =============================================================================

# Configuración de migración YAML -> DB
MIGRATION_BACKUP_ENABLED = os.getenv("MIGRATION_BACKUP_ENABLED", "true").lower() == "true"
MIGRATION_BACKUP_PATH = os.getenv("MIGRATION_BACKUP_PATH", "/app/backups")
MIGRATION_VALIDATE_BEFORE = os.getenv("MIGRATION_VALIDATE_BEFORE", "true").lower() == "true"

# Configuración de rollback
ROLLBACK_TIMEOUT_MINUTES = int(os.getenv("ROLLBACK_TIMEOUT_MINUTES", "5"))
ROLLBACK_TRIGGER_ERROR_RATE = float(os.getenv("ROLLBACK_TRIGGER_ERROR_RATE", "5.0"))  # %

# =============================================================================
# PROVIDERS DEVELOPMENT CONFIGURATION
# =============================================================================

# Configuración específica para desarrollo
DEV_MOCK_PROVIDERS_ENABLED = os.getenv("DEV_MOCK_PROVIDERS_ENABLED", "false").lower() == "true"
DEV_FORCE_PROVIDER = os.getenv("DEV_FORCE_PROVIDER", "")  # Forzar un provider específico
DEV_SIMULATE_FAILURES = os.getenv("DEV_SIMULATE_FAILURES", "false").lower() == "true"
DEV_FAILURE_RATE = float(os.getenv("DEV_FAILURE_RATE", "0.1"))  # 10%

# Debug de providers
DEBUG_PROVIDERS_ENABLED = os.getenv("DEBUG_PROVIDERS_ENABLED", "false").lower() == "true"
DEBUG_LOG_PROVIDER_CALLS = os.getenv("DEBUG_LOG_PROVIDER_CALLS", "false").lower() == "true"
DEBUG_LOG_PROVIDER_RESPONSES = os.getenv("DEBUG_LOG_PROVIDER_RESPONSES", "false").lower() == "true"

# =============================================================================
# PROVIDERS FEATURE FLAGS
# =============================================================================

# Feature flags para funcionalidades de providers
FEATURE_PROVIDER_GROUPS_ENABLED = os.getenv("FEATURE_PROVIDER_GROUPS_ENABLED", "true").lower() == "true"
FEATURE_PROVIDER_HEALTH_CHECKS_ENABLED = os.getenv("FEATURE_PROVIDER_HEALTH_CHECKS_ENABLED", "true").lower() == "true"
FEATURE_PROVIDER_LOAD_BALANCING_ENABLED = os.getenv("FEATURE_PROVIDER_LOAD_BALANCING_ENABLED", "true").lower() == "true"
FEATURE_PROVIDER_COST_TRACKING_ENABLED = os.getenv("FEATURE_PROVIDER_COST_TRACKING_ENABLED", "false").lower() == "true"

# Funcionalidades experimentales
FEATURE_PROVIDER_AUTO_SCALING = os.getenv("FEATURE_PROVIDER_AUTO_SCALING", "false").lower() == "true"
FEATURE_PROVIDER_ML_ROUTING = os.getenv("FEATURE_PROVIDER_ML_ROUTING", "false").lower() == "true"

# =============================================================================
# PROVIDERS ERROR HANDLING
# =============================================================================

# Configuración de manejo de errores
ERROR_RETRY_EXPONENTIAL_BACKOFF = os.getenv("ERROR_RETRY_EXPONENTIAL_BACKOFF", "true").lower() == "true"
ERROR_RETRY_MAX_DELAY_SECONDS = int(os.getenv("ERROR_RETRY_MAX_DELAY_SECONDS", "300"))  # 5 minutos
ERROR_RETRY_JITTER_ENABLED = os.getenv("ERROR_RETRY_JITTER_ENABLED", "true").lower() == "true"

# Circuit breaker configuration
CIRCUIT_BREAKER_ENABLED = os.getenv("CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60"))  # segundos

# =============================================================================
# PROVIDERS STATUS CODES
# =============================================================================

# Códigos de estado específicos para providers
PROVIDER_STATUS_HEALTHY = "healthy"
PROVIDER_STATUS_UNHEALTHY = "unhealthy"
PROVIDER_STATUS_DEGRADED = "degraded"
PROVIDER_STATUS_MAINTENANCE = "maintenance"
PROVIDER_STATUS_DISABLED = "disabled"

PROVIDER_HEALTH_STATUSES = [
    PROVIDER_STATUS_HEALTHY,
    PROVIDER_STATUS_UNHEALTHY,
    PROVIDER_STATUS_DEGRADED,
    PROVIDER_STATUS_MAINTENANCE,
    PROVIDER_STATUS_DISABLED
]

# =============================================================================
# PROVIDERS ADMIN API CONFIGURATION
# =============================================================================

# Configuración de endpoints administrativos
ADMIN_PROVIDERS_ENDPOINT_ENABLED = os.getenv("ADMIN_PROVIDERS_ENDPOINT_ENABLED", "true").lower() == "true"
ADMIN_PROVIDERS_REQUIRE_AUTH = os.getenv("ADMIN_PROVIDERS_REQUIRE_AUTH", "true").lower() == "true"
ADMIN_PROVIDERS_AUDIT_ENABLED = os.getenv("ADMIN_PROVIDERS_AUDIT_ENABLED", "true").lower() == "true"

# Límites de API administrativa
ADMIN_PROVIDERS_RATE_LIMIT = int(os.getenv("ADMIN_PROVIDERS_RATE_LIMIT", "100"))  # requests/hour
ADMIN_PROVIDERS_BULK_LIMIT = int(os.getenv("ADMIN_PROVIDERS_BULK_LIMIT", "50"))  # providers por request

# =============================================================================
# COMPATIBILITY FLAGS
# =============================================================================

# Compatibilidad hacia atrás
LEGACY_YAML_SUPPORT_ENABLED = os.getenv("LEGACY_YAML_SUPPORT_ENABLED", "true").lower() == "true"
LEGACY_CONFIG_FORMAT_SUPPORT = os.getenv("LEGACY_CONFIG_FORMAT_SUPPORT", "true").lower() == "true"

# Migración gradual
GRADUAL_MIGRATION_ENABLED = os.getenv("GRADUAL_MIGRATION_ENABLED", "true").lower() == "true"
MIGRATION_PERCENTAGE = int(os.getenv("MIGRATION_PERCENTAGE", "0"))  # % de providers que usan DB

# =============================================================================
# ENVIRONMENT SPECIFIC OVERRIDES
# =============================================================================

# Overrides específicos por ambiente
# En desarrollo, usar valores más permisivos
PROVIDERS_MAX_LOAD_TIME_MS = 200
HEALTH_CHECK_DEFAULT_INTERVAL = 10
DEBUG_PROVIDERS_ENABLED = True
USE_DATABASE_PROVIDERS = False  # YAML por defecto en dev

# En producción, usar valores más estrictos
# PROVIDERS_MAX_LOAD_TIME_MS = 30
# HEALTH_CHECK_DEFAULT_INTERVAL = 5
# DEBUG_PROVIDERS_ENABLED = False
# CIRCUIT_BREAKER_ENABLED = True
# METRICS_PROVIDERS_ENABLED = True