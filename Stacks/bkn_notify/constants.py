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