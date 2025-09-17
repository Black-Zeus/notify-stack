"""
Stacks/bkn_notify/models/database_models.py
Database Models - SQLAlchemy ORM
Modelos para las tablas del sistema de notificaciones
"""

from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import (
    Column, BigInteger, String, Text, Integer, 
    DateTime, JSON, Enum as SQLEnum, ForeignKey, Index,
    Date, SmallInteger  # ✅ AGREGADO: Date y SmallInteger para ProviderStats
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class NotificationStatus(str, Enum):
    """Estados posibles de una notificación - ✅ CORREGIDO: valores en UPPERCASE"""
    PENDING = "PENDING"          # Era "pending"
    PROCESSING = "PROCESSING"    # Era "processing"
    SENT = "SENT"               # Era "sent"
    FAILED = "FAILED"           # Era "failed" 
    REJECTED = "REJECTED"       # Era "rejected"


class NotificationPriority(str, Enum):
    """Prioridades de notificación - ✅ CORREGIDO: valores en UPPERCASE"""
    LOW = "LOW"          # Era "low"
    MEDIUM = "MEDIUM"    # Era "medium" 
    HIGH = "HIGH"        # Era "high"


class Notification(Base):
    """
    Modelo principal para notificaciones
    Corresponde a la tabla 'notifications'
    """
    __tablename__ = "notifications"

    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)

    # Template info
    template_id = Column(String(100), nullable=True, index=True)
    template_version = Column(String(20), nullable=True)

    # Recipients
    to_email = Column(String(500), nullable=False, index=True)
    cc_emails = Column(JSON, nullable=True)
    bcc_emails = Column(JSON, nullable=True)

    # Content
    subject = Column(String(1000), nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)

    # Sending config
    provider = Column(String(50), nullable=True, index=True)
    routing_hint = Column(String(100), nullable=True)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.MEDIUM)

    # Template variables (JSON)
    params_json = Column(JSON, nullable=True)

    # Metadata
    idempotency_key = Column(String(255), nullable=True)
    celery_task_id = Column(String(255), nullable=True, index=True)

    # Status
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING, index=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Origin metadata
    source_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    api_key_hash = Column(String(64), nullable=True)

    # Relationships
    logs = relationship("NotificationLog", back_populates="notification", cascade="all, delete-orphan")
    attachments = relationship("NotificationAttachment", back_populates="notification", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Notification(message_id='{self.message_id}', status='{self.status}', to='{self.to_email}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "to_email": self.to_email,
            "cc_emails": self.cc_emails,
            "bcc_emails": self.bcc_emails,
            "subject": self.subject,
            "provider": self.provider,
            "routing_hint": self.routing_hint,
            "priority": self.priority.value if self.priority else None,
            "params_json": self.params_json,
            "idempotency_key": self.idempotency_key,
            "celery_task_id": self.celery_task_id,
            "status": self.status.value if self.status else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent
        }


class NotificationLog(Base):
    """
    Modelo para logs de eventos de notificaciones
    Corresponde a la tabla 'notification_logs'
    """
    __tablename__ = "notification_logs"

    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(String(255), ForeignKey("notifications.message_id", ondelete="CASCADE"), nullable=False, index=True)

    # Event info
    event_type = Column(String(50), nullable=False, index=True)
    event_status = Column(String(50), nullable=True)

    # Event details
    event_message = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=True)

    # Technical context
    component = Column(String(50), nullable=True, index=True)  # 'api', 'celery', 'smtp'
    provider = Column(String(50), nullable=True)

    # Metrics
    processing_time_ms = Column(Integer, nullable=True)

    # Timestamp
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)

    # Relationships
    notification = relationship("Notification", back_populates="logs")

    def __repr__(self):
        return f"<NotificationLog(message_id='{self.message_id}', event='{self.event_type}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "event_type": self.event_type,
            "event_status": self.event_status,
            "event_message": self.event_message,
            "details_json": self.details_json,
            "component": self.component,
            "provider": self.provider,
            "processing_time_ms": self.processing_time_ms,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class NotificationAttachment(Base):
    """
    Modelo para archivos adjuntos de notificaciones
    Corresponde a la tabla 'notification_attachments'
    """
    __tablename__ = "notification_attachments"

    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(String(255), ForeignKey("notifications.message_id", ondelete="CASCADE"), nullable=False, index=True)

    # File info
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)

    # File verification
    file_hash = Column(String(64), nullable=True)

    # Storage info (future: S3, local, etc.)
    storage_type = Column(String(20), default="local")
    storage_path = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    notification = relationship("Notification", back_populates="attachments")

    def __repr__(self):
        return f"<NotificationAttachment(message_id='{self.message_id}', filename='{self.filename}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "file_hash": self.file_hash,
            "storage_type": self.storage_type,
            "storage_path": self.storage_path,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ProviderStats(Base):
    """
    ✅ CORREGIDO: Modelo para estadísticas de proveedores 
    Coincide exactamente con la tabla SQL provider_stats
    """
    __tablename__ = "provider_stats"

    # ✅ NO PRIMARY KEY ID - La tabla SQL no tiene campo id
    
    # Clave compuesta (provider + stat_date + stat_hour)
    provider = Column(String(50), primary_key=True, nullable=False)
    stat_date = Column(Date, primary_key=True, nullable=False)
    stat_hour = Column(SmallInteger, primary_key=True, nullable=True)  # TINYINT UNSIGNED = SmallInteger
    
    # Contadores de estadísticas
    total_sent = Column(Integer, default=0, nullable=False)
    total_failed = Column(Integer, default=0, nullable=False)
    total_rejected = Column(Integer, default=0, nullable=False)
    
    # Métricas de tiempo
    avg_processing_time_ms = Column(Integer, nullable=True)
    max_processing_time_ms = Column(Integer, nullable=True)

    # Índices
    __table_args__ = (
        Index('idx_provider_stats_date', 'provider', 'stat_date'),
        Index('idx_provider_stats_hour', 'provider', 'stat_date', 'stat_hour'),
    )

    def __repr__(self):
        return f"<ProviderStats(provider='{self.provider}', date='{self.stat_date}', hour={self.stat_hour})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "provider": self.provider,
            "stat_date": self.stat_date.isoformat() if self.stat_date else None,
            "stat_hour": self.stat_hour,
            "total_sent": self.total_sent,
            "total_failed": self.total_failed,
            "total_rejected": self.total_rejected,
            "avg_processing_time_ms": self.avg_processing_time_ms,
            "max_processing_time_ms": self.max_processing_time_ms
        }


# ✅ FUNCIONES DE UTILIDAD PARA ENUMS

def get_priority_from_string(priority_str: str) -> NotificationPriority:
    """Convierte string a enum NotificationPriority"""
    if not priority_str:
        return NotificationPriority.MEDIUM
    
    priority_upper = priority_str.upper()
    if priority_upper == "LOW":
        return NotificationPriority.LOW
    elif priority_upper == "MEDIUM":
        return NotificationPriority.MEDIUM
    elif priority_upper == "HIGH":
        return NotificationPriority.HIGH
    else:
        return NotificationPriority.MEDIUM  # Default


def get_status_from_string(status_str: str) -> NotificationStatus:
    """Convierte string a enum NotificationStatus"""
    if not status_str:
        return NotificationStatus.PENDING
    
    status_lower = status_str.upper()
    if status_lower == "PENDING":
        return NotificationStatus.PENDING
    elif status_lower == "PROCESSING":
        return NotificationStatus.PROCESSING
    elif status_lower == "SENT":
        return NotificationStatus.SENT
    elif status_lower == "FAILED":
        return NotificationStatus.FAILED
    elif status_lower == "REJECTED":
        return NotificationStatus.REJECTED
    else:
        return NotificationStatus.PENDING  # Default