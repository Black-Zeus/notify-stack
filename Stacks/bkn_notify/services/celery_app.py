"""
Celery app configuration - Fixed Imports
Configuración centralizada de Celery para el sistema de notificaciones
"""

import os
import sys
import logging
from celery import Celery
from celery.signals import after_setup_logger

# Agregar directorio raíz al path para imports absolutos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Imports absolutos con fallbacks
try:
    import constants
except ImportError:
    # Fallback si constants.py no está disponible
    class Constants:
        CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://bkn_redis:6379/0")
        CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://bkn_redis:6379/0")
        CELERY_TASK_SERIALIZER = "json"
        CELERY_RESULT_SERIALIZER = "json"
        CELERY_TASK_TIMEOUT = int(os.getenv("CELERY_TASK_TIMEOUT", "300"))
        MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
        RETRY_BACKOFF = int(os.getenv("RETRY_BACKOFF", "2"))
    constants = Constants()

# Crear instancia Celery
celery_app = Celery('notify-celery')

# Configuración de Celery
celery_app.conf.update(
    # Broker y backend
    broker_url=getattr(constants, 'CELERY_BROKER_URL', 'redis://bkn_redis:6379/0'),
    result_backend=getattr(constants, 'CELERY_RESULT_BACKEND', 'redis://bkn_redis:6379/0'),
    
    # Serialización
    task_serializer=getattr(constants, 'CELERY_TASK_SERIALIZER', 'json'),
    result_serializer=getattr(constants, 'CELERY_RESULT_SERIALIZER', 'json'),
    accept_content=['json'],
    
    # Timeouts y retries
    task_time_limit=getattr(constants, 'CELERY_TASK_TIMEOUT', 300),
    task_soft_time_limit=getattr(constants, 'CELERY_TASK_TIMEOUT', 300) - 30,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    
    # Configuración de tareas
    task_routes={
        'services.celery_tasks.send_notification_task': {'queue': 'notifications'},
        'services.celery_tasks.send_test_notification_task': {'queue': 'test'},
        'services.celery_tasks.cleanup_old_logs_task': {'queue': 'maintenance'},
    },
    
    # Configuración de colas
    task_default_queue='notifications',
    task_create_missing_queues=True,
    
    # Retry policy por defecto
    task_default_retry_delay=60,  # 1 minuto
    task_max_retries=getattr(constants, 'MAX_RETRIES', 3),
    task_retry_backoff=getattr(constants, 'RETRY_BACKOFF', 2),
    task_retry_backoff_max=600,  # 10 minutos máximo
    task_retry_jitter=True,
    
    # Configuración de workers
    worker_hijack_root_logger=False,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # Configuración de resultados
    result_expires=3600,  # 1 hora
    result_compression='gzip',
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Security
    worker_disable_rate_limits=False,
    task_reject_on_worker_lost=True,

    broker_connection_retry_on_startup=True,
)

# Autodiscovery de tareas (con manejo de errores)
try:
    celery_app.autodiscover_tasks([
        'services.celery_tasks',
    ])
except ImportError:
    logging.warning("celery_tasks module not found - no tasks will be autodiscovered")


@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    """
    Configurar logging para Celery workers
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def get_celery_app() -> Celery:
    """
    Obtiene instancia de Celery app
    """
    return celery_app


# ====================================================================
# FUNCIONES PLACEHOLDER ELIMINADAS
# ====================================================================
# La función send_notification_task() fue eliminada de aquí para evitar
# conflictos con la versión completa en services/celery_tasks.py
# 
# ANTES había:
# @celery_app.task(bind=True)
# def send_notification_task(self, payload): ...
# 
# Esto causaba que los logs no se registraran en MySQL porque
# esta versión placeholder tenía precedencia sobre la versión
# completa con integración a base de datos.
# ====================================================================


@celery_app.task
def health_check_task():
    """
    Tarea de health check para verificar que Celery funciona
    """
    return {
        "status": "healthy",
        "worker": "celery",
        "timestamp": "2024-01-01T00:00:00Z"
    }


@celery_app.task
def cleanup_old_logs_task():
    """
    Placeholder para limpieza de logs antiguos
    """
    logging.info("Cleanup task executed (placeholder)")
    return {"cleaned": 0, "status": "placeholder"}


def test_celery_connection() -> bool:
    """
    Prueba conexión a broker y backend de Celery
    """
    try:
        # Test broker connection
        broker_connection = celery_app.connection()
        broker_connection.ensure_connection(max_retries=3)
        broker_connection.release()
        
        logging.info("Celery connection test passed")
        return True
        
    except Exception as e:
        logging.error(f"Celery connection test failed: {e}")
        return False


def get_celery_info() -> dict:
    """
    Obtiene información del estado de Celery
    """
    try:
        return {
            'app_name': celery_app.main,
            'broker_url': celery_app.conf.broker_url,
            'result_backend': celery_app.conf.result_backend,
            'registered_tasks': list(celery_app.tasks.keys()),
            'default_queue': celery_app.conf.task_default_queue,
            'task_serializer': celery_app.conf.task_serializer,
            'result_serializer': celery_app.conf.result_serializer
        }
    except Exception as e:
        logging.error(f"Error getting Celery info: {e}")
        return {
            'error': str(e),
            'app_name': celery_app.main
        }


# Configurar app al importar (solo si se ejecuta directamente)
if __name__ == '__main__':
    logging.info("Celery app initialized")