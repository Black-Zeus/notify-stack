"""
Database Utils - Conexión y configuración de base de datos
Gestión de sesiones SQLAlchemy y configuración MySQL
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError

from models.database_models import Base

logger = logging.getLogger(__name__)

# Variables globales para engine y session factory
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_database_url() -> str:
    """Construye URL de conexión desde variables de entorno"""
    
    host = os.getenv("MYSQL_HOST", "mysql")
    port = os.getenv("MYSQL_PORT", "3306")
    user = os.getenv("MYSQL_USER", "notify_user")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_DATABASE", "notify_db")
    
    if not password:
        raise ValueError("MYSQL_PASSWORD environment variable is required")
    
    # URL con configuración optimizada para MySQL
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    url += "?charset=utf8mb4&autocommit=false"
    
    return url


def create_database_engine() -> Engine:
    """Crea engine de SQLAlchemy con configuración optimizada"""
    
    database_url = get_database_url()
    
    # Configuración del engine
    engine = create_engine(
        database_url,
        
        # Pool settings
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        
        # Connection settings
        connect_args={
            "charset": "utf8mb4",
            "autocommit": False,
            "connect_timeout": 30,
            "read_timeout": 30,
            "write_timeout": 30
        },
        
        # Logging
        echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        echo_pool=False,
        
        # Performance
        isolation_level="READ_COMMITTED",
        future=True
    )
    
    # Event listeners para optimización
    @event.listens_for(engine, "connect")
    def set_mysql_pragma(dbapi_connection, connection_record):
        """Configura parámetros de conexión MySQL"""
        try:
            cursor = dbapi_connection.cursor()
            
            # Configuraciones MySQL optimizadas
            cursor.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO'")
            cursor.execute("SET SESSION innodb_lock_wait_timeout = 50")
            cursor.execute("SET SESSION lock_wait_timeout = 50")
            cursor.execute("SET SESSION interactive_timeout = 28800")
            cursor.execute("SET SESSION wait_timeout = 28800")
            
            cursor.close()
            
        except Exception as e:
            logger.warning(f"Could not set MySQL pragmas: {e}")
    
    logger.info("Database engine created successfully")
    return engine


def initialize_database() -> bool:
    """Inicializa la base de datos y crea tablas si no existen"""
    
    global _engine, _SessionLocal
    
    try:
        # Crear engine
        _engine = create_database_engine()
        
        # Crear session factory
        _SessionLocal = sessionmaker(
            bind=_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
        # Crear tablas si no existen
        Base.metadata.create_all(bind=_engine)
        
        # Verificar conexión
        with get_db_session() as db:
            db.execute("SELECT 1")
        
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def get_database_engine() -> Engine:
    """Obtiene el engine de base de datos"""
    
    global _engine
    
    if _engine is None:
        if not initialize_database():
            raise RuntimeError("Failed to initialize database")
    
    return _engine


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager para sesiones de base de datos"""
    
    global _SessionLocal
    
    if _SessionLocal is None:
        if not initialize_database():
            raise RuntimeError("Failed to initialize database")
    
    session = _SessionLocal()
    
    try:
        yield session
        session.commit()
        
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
        
    except Exception as e:
        session.rollback()
        logger.error(f"Unexpected error in database session: {e}")
        raise
        
    finally:
        session.close()


def get_db_session_factory() -> sessionmaker:
    """Obtiene la factory de sesiones"""
    
    global _SessionLocal
    
    if _SessionLocal is None:
        if not initialize_database():
            raise RuntimeError("Failed to initialize database")
    
    return _SessionLocal


def check_database_health() -> bool:
    """Verifica el estado de la base de datos"""
    
    try:
        with get_db_session() as db:
            result = db.execute("SELECT 1 as health_check").fetchone()
            return result[0] == 1
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def get_database_info() -> dict:
    """Obtiene información de la base de datos"""
    
    try:
        with get_db_session() as db:
            # Información de MySQL
            version_result = db.execute("SELECT VERSION() as version").fetchone()
            charset_result = db.execute("SELECT @@character_set_database as charset").fetchone()
            
            # Estadísticas de conexiones
            engine = get_database_engine()
            pool = engine.pool
            
            return {
                "mysql_version": version_result[0] if version_result else "unknown",
                "charset": charset_result[0] if charset_result else "unknown",
                "pool_size": pool.size(),
                "checked_out_connections": pool.checkedout(),
                "checked_in_connections": pool.checkedin(),
                "overflow_connections": pool.overflow(),
                "invalid_connections": pool.invalidated(),
                "database_url_masked": get_database_url().split('@')[1] if '@' in get_database_url() else "unknown"
            }
            
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {"error": str(e)}


def close_database_connections():
    """Cierra todas las conexiones de base de datos"""
    
    global _engine, _SessionLocal
    
    try:
        if _engine:
            _engine.dispose()
            _engine = None
            
        if _SessionLocal:
            _SessionLocal.close_all()
            _SessionLocal = None
            
        logger.info("Database connections closed")
        
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


# Funciones de utilidad para testing y desarrollo

def reset_database():
    """Reinicia la base de datos (solo para desarrollo/testing)"""
    
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError("Cannot reset database in production")
    
    try:
        engine = get_database_engine()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        logger.warning("Database reset completed")
        return True
        
    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        return False


def execute_raw_sql(sql: str, params: Optional[dict] = None) -> list:
    """Ejecuta SQL crudo (solo para operaciones especiales)"""
    
    try:
        with get_db_session() as db:
            result = db.execute(sql, params or {})
            
            if result.returns_rows:
                return result.fetchall()
            else:
                return []
                
    except Exception as e:
        logger.error(f"Failed to execute raw SQL: {e}")
        raise