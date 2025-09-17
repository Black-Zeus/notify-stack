"""
Stacks/bkn_notify/models/provider_models.py
Provider Models - SQLAlchemy ORM para providers
Modelos específicos para tablas de proveedores y grupos
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, JSON, 
    Enum as SQLEnum, ForeignKey, Index, DECIMAL
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.database_models import Base


# =============================================================================
# ENUMS
# =============================================================================

class ProviderType(str, Enum):
    """Tipos de proveedores de notificación"""
    SMTP = "smtp"
    API = "api"
    WEBHOOK = "webhook"
    TWILIO = "twilio"


class ProviderEnvironment(str, Enum):
    """Ambientes de deployment"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class RoutingStrategy(str, Enum):
    """Estrategias de routing en grupos"""
    PRIORITY = "priority"
    ROUND_ROBIN = "round_robin"
    FAILOVER = "failover"
    LOAD_BALANCE = "load_balance"
    RANDOM = "random"


class HealthCheckType(str, Enum):
    """Tipos de health check"""
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    STARTUP = "startup"
    SCHEDULED = "scheduled"
    ON_DEMAND = "on_demand"


class HealthCheckMethod(str, Enum):
    """Métodos de health check"""
    GET = "GET"
    POST = "POST"
    HEAD = "HEAD"
    SMTP = "SMTP"
    API = "API"


class IncidentStatus(str, Enum):
    """Estados de incidentes"""
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSeverity(str, Enum):
    """Severidad de incidentes"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# MODELS
# =============================================================================

class Provider(Base):
    """
    Modelo para tabla providers
    Configuración principal de proveedores de notificación
    """
    __tablename__ = "providers"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identificador único
    provider_key = Column(String(50), unique=True, nullable=False, index=True)
    
    # Información básica
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    provider_type = Column(SQLEnum(ProviderType), nullable=False, index=True)
    
    # Estado y configuración
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    priority = Column(Integer, default=100, nullable=False)
    weight = Column(Integer, default=10, nullable=False)
    
    # Límites y configuración
    max_retries = Column(Integer, default=3, nullable=False)
    timeout_seconds = Column(Integer, default=30, nullable=False)
    rate_limit_per_minute = Column(Integer, default=60, nullable=False)
    
    # Configuración específica del proveedor (JSON)
    config_json = Column(JSON, nullable=False)
    
    # Credenciales cifradas (JSON)
    credentials_json = Column(JSON, nullable=True)
    
    # Configuración de salud y monitoreo
    health_check_enabled = Column(Boolean, default=True, nullable=False)
    health_check_url = Column(String(500), nullable=True)
    health_check_interval_minutes = Column(Integer, default=5, nullable=False)
    
    # Estados de operación
    is_healthy = Column(Boolean, default=True, nullable=False, index=True)
    last_health_check = Column(DateTime, nullable=True)
    last_error_message = Column(Text, nullable=True)
    
    # Metadatos de gestión
    environment = Column(SQLEnum(ProviderEnvironment), default=ProviderEnvironment.PRODUCTION, nullable=False, index=True)
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    health_checks = relationship("ProviderHealthCheck", back_populates="provider", cascade="all, delete-orphan")
    health_config = relationship("ProviderHealthConfig", back_populates="provider", uselist=False, cascade="all, delete-orphan")
    group_memberships = relationship("ProviderGroupMember", back_populates="provider", cascade="all, delete-orphan")
    incidents = relationship("ProviderHealthIncident", back_populates="provider", cascade="all, delete-orphan")
    metrics = relationship("ProviderHealthMetric", back_populates="provider", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Provider(key='{self.provider_key}', name='{self.name}', type='{self.provider_type}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "provider_key": self.provider_key,
            "name": self.name,
            "description": self.description,
            "provider_type": self.provider_type.value if self.provider_type else None,
            "enabled": self.enabled,
            "priority": self.priority,
            "weight": self.weight,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "config_json": self.config_json,
            "health_check_enabled": self.health_check_enabled,
            "health_check_url": self.health_check_url,
            "health_check_interval_minutes": self.health_check_interval_minutes,
            "is_healthy": self.is_healthy,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "last_error_message": self.last_error_message,
            "environment": self.environment.value if self.environment else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def is_active(self) -> bool:
        """Verifica si el proveedor está activo y saludable"""
        return self.enabled and self.is_healthy


class ProviderGroup(Base):
    """
    Modelo para tabla provider_groups
    Agrupación lógica de proveedores para routing
    """
    __tablename__ = "provider_groups"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identificador único del grupo
    group_key = Column(String(50), unique=True, nullable=False, index=True)
    
    # Información básica
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Estrategia de routing dentro del grupo
    routing_strategy = Column(SQLEnum(RoutingStrategy), default=RoutingStrategy.PRIORITY, nullable=False, index=True)
    
    # Configuración de failover
    failover_enabled = Column(Boolean, default=True, nullable=False)
    failover_timeout_seconds = Column(Integer, default=30, nullable=False)
    
    # Configuración de retry
    max_group_retries = Column(Integer, default=2, nullable=False)
    retry_delay_seconds = Column(Integer, default=5, nullable=False)
    
    # Estado del grupo
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    
    # Metadatos de gestión
    environment = Column(SQLEnum(ProviderEnvironment), default=ProviderEnvironment.PRODUCTION, nullable=False, index=True)
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    members = relationship("ProviderGroupMember", back_populates="group", cascade="all, delete-orphan")
    routing_rules = relationship("ProviderGroupRouting", foreign_keys="ProviderGroupRouting.target_group_id", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProviderGroup(key='{self.group_key}', name='{self.name}', strategy='{self.routing_strategy}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "group_key": self.group_key,
            "name": self.name,
            "description": self.description,
            "routing_strategy": self.routing_strategy.value if self.routing_strategy else None,
            "failover_enabled": self.failover_enabled,
            "failover_timeout_seconds": self.failover_timeout_seconds,
            "max_group_retries": self.max_group_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "enabled": self.enabled,
            "environment": self.environment.value if self.environment else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ProviderGroupMember(Base):
    """
    Modelo para tabla provider_group_members
    Relación N:N entre grupos y proveedores
    """
    __tablename__ = "provider_group_members"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Referencias a grupo y proveedor
    group_id = Column(Integer, ForeignKey("provider_groups.id"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False, index=True)
    
    # Configuración dentro del grupo
    priority = Column(Integer, default=100, nullable=False)
    weight = Column(Integer, default=10, nullable=False)
    
    # Estado específico en el grupo
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Configuración de failover específica del miembro
    max_member_retries = Column(Integer, default=3, nullable=False)
    timeout_override_seconds = Column(Integer, nullable=True)
    
    # Configuración de load balancing
    capacity_limit = Column(Integer, nullable=True)
    current_load = Column(Integer, default=0, nullable=False)
    
    # Metadatos
    added_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    group = relationship("ProviderGroup", back_populates="members")
    provider = relationship("Provider", back_populates="group_memberships")

    # Índices compuestos
    __table_args__ = (
        Index("idx_group_provider", "group_id", "provider_id", unique=True),
        Index("idx_group_enabled_priority", "group_id", "enabled", "priority"),
    )

    def __repr__(self):
        return f"<ProviderGroupMember(group_id={self.group_id}, provider_id={self.provider_id}, priority={self.priority})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "group_id": self.group_id,
            "provider_id": self.provider_id,
            "priority": self.priority,
            "weight": self.weight,
            "enabled": self.enabled,
            "max_member_retries": self.max_member_retries,
            "timeout_override_seconds": self.timeout_override_seconds,
            "capacity_limit": self.capacity_limit,
            "current_load": self.current_load,
            "added_by": self.added_by,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ProviderGroupRouting(Base):
    """
    Modelo para tabla provider_group_routing
    Configuración de routing hacia grupos de proveedores
    """
    __tablename__ = "provider_group_routing"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Identificador de la regla de routing
    route_key = Column(String(50), unique=True, nullable=False, index=True)
    
    # Información básica
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Target del routing
    target_group_id = Column(Integer, ForeignKey("provider_groups.id"), nullable=False, index=True)
    fallback_group_id = Column(Integer, ForeignKey("provider_groups.id"), nullable=True, index=True)
    
    # Condiciones de activación (JSON)
    conditions_json = Column(JSON, nullable=True)
    
    # Configuración de la regla
    priority = Column(Integer, default=100, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    
    # Metadatos
    environment = Column(SQLEnum(ProviderEnvironment), default=ProviderEnvironment.PRODUCTION, nullable=False, index=True)
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    target_group = relationship("ProviderGroup", foreign_keys=[target_group_id])
    fallback_group = relationship("ProviderGroup", foreign_keys=[fallback_group_id])

    def __repr__(self):
        return f"<ProviderGroupRouting(route_key='{self.route_key}', target_group_id={self.target_group_id})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "route_key": self.route_key,
            "name": self.name,
            "description": self.description,
            "target_group_id": self.target_group_id,
            "fallback_group_id": self.fallback_group_id,
            "conditions_json": self.conditions_json,
            "priority": self.priority,
            "enabled": self.enabled,
            "environment": self.environment.value if self.environment else None,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ProviderHealthCheck(Base):
    """
    Modelo para tabla provider_health_checks
    Historial detallado de health checks
    """
    __tablename__ = "provider_health_checks"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Referencia al proveedor
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False, index=True)
    
    # Resultado del health check
    is_healthy = Column(Boolean, nullable=False, index=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Detalles técnicos
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Metadata del check
    check_type = Column(SQLEnum(HealthCheckType), default=HealthCheckType.AUTOMATIC, nullable=False, index=True)
    check_endpoint = Column(String(500), nullable=True)
    check_method = Column(SQLEnum(HealthCheckMethod), default=HealthCheckMethod.GET, nullable=False)
    
    # Contexto del check
    checked_by = Column(String(100), nullable=True)
    check_source = Column(String(50), nullable=True)
    request_id = Column(String(255), nullable=True)
    
    # Timestamp
    checked_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    
    # Relationships
    provider = relationship("Provider", back_populates="health_checks")

    def __repr__(self):
        return f"<ProviderHealthCheck(provider_id={self.provider_id}, is_healthy={self.is_healthy}, checked_at='{self.checked_at}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "is_healthy": self.is_healthy,
            "response_time_ms": self.response_time_ms,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "check_type": self.check_type.value if self.check_type else None,
            "check_method": self.check_method.value if self.check_method else None,
            "checked_by": self.checked_by,
            "check_source": self.check_source,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None
        }


class ProviderHealthConfig(Base):
    """
    Modelo para tabla provider_health_config
    Configuración específica de health checks por proveedor
    """
    __tablename__ = "provider_health_config"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Referencia al proveedor (único)
    provider_id = Column(Integer, ForeignKey("providers.id"), unique=True, nullable=False, index=True)
    
    # Configuración del health check
    enabled = Column(Boolean, default=True, nullable=False)
    check_interval_minutes = Column(Integer, default=5, nullable=False)
    timeout_seconds = Column(Integer, default=30, nullable=False)
    
    # Endpoint y método de verificación
    health_check_url = Column(String(500), nullable=True)
    check_method = Column(SQLEnum(HealthCheckMethod), default=HealthCheckMethod.GET, nullable=False)
    expected_status_code = Column(Integer, default=200, nullable=False)
    expected_response_pattern = Column(String(500), nullable=True)
    
    # Headers y auth para el check (JSON)
    check_headers = Column(JSON, nullable=True)
    check_auth = Column(JSON, nullable=True)
    
    # Criterios de salud
    consecutive_failures_threshold = Column(Integer, default=3, nullable=False)
    consecutive_successes_threshold = Column(Integer, default=2, nullable=False)
    max_response_time_ms = Column(Integer, default=5000, nullable=False)
    
    # Configuración de alertas
    alert_on_failure = Column(Boolean, default=True, nullable=False)
    alert_on_recovery = Column(Boolean, default=True, nullable=False)
    alert_recipients = Column(JSON, nullable=True)
    
    # Metadatos
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    provider = relationship("Provider", back_populates="health_config")

    def __repr__(self):
        return f"<ProviderHealthConfig(provider_id={self.provider_id}, enabled={self.enabled})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "enabled": self.enabled,
            "check_interval_minutes": self.check_interval_minutes,
            "timeout_seconds": self.timeout_seconds,
            "health_check_url": self.health_check_url,
            "check_method": self.check_method.value if self.check_method else None,
            "expected_status_code": self.expected_status_code,
            "expected_response_pattern": self.expected_response_pattern,
            "consecutive_failures_threshold": self.consecutive_failures_threshold,
            "consecutive_successes_threshold": self.consecutive_successes_threshold,
            "max_response_time_ms": self.max_response_time_ms,
            "alert_on_failure": self.alert_on_failure,
            "alert_on_recovery": self.alert_on_recovery,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ProviderHealthIncident(Base):
    """
    Modelo para tabla provider_health_incidents
    Registro de incidentes y problemas de proveedores
    """
    __tablename__ = "provider_health_incidents"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Referencia al proveedor
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False, index=True)
    
    # Información del incidente
    incident_key = Column(String(100), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Estado del incidente
    status = Column(SQLEnum(IncidentStatus), default=IncidentStatus.OPEN, nullable=False, index=True)
    severity = Column(SQLEnum(IncidentSeverity), default=IncidentSeverity.MEDIUM, nullable=False, index=True)
    
    # Impacto
    impact_description = Column(Text, nullable=True)
    affected_operations = Column(JSON, nullable=True)
    estimated_downtime_minutes = Column(Integer, nullable=True)
    
    # Resolución
    resolution_notes = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    preventive_actions = Column(Text, nullable=True)
    
    # Timestamps de ciclo de vida
    detected_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Responsables
    assigned_to = Column(String(100), nullable=True)
    resolved_by = Column(String(100), nullable=True)
    
    # Metadatos
    created_by = Column(String(100), nullable=True)
    
    # Relationships
    provider = relationship("Provider", back_populates="incidents")

    # Índices compuestos
    __table_args__ = (
        Index("idx_provider_incident", "provider_id", "incident_key", unique=True),
        Index("idx_provider_status", "provider_id", "status"),
    )

    def __repr__(self):
        return f"<ProviderHealthIncident(provider_id={self.provider_id}, incident_key='{self.incident_key}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "incident_key": self.incident_key,
            "title": self.title,
            "description": self.description,
            "status": self.status.value if self.status else None,
            "severity": self.severity.value if self.severity else None,
            "impact_description": self.impact_description,
            "affected_operations": self.affected_operations,
            "estimated_downtime_minutes": self.estimated_downtime_minutes,
            "resolution_notes": self.resolution_notes,
            "root_cause": self.root_cause,
            "preventive_actions": self.preventive_actions,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "assigned_to": self.assigned_to,
            "resolved_by": self.resolved_by,
            "created_by": self.created_by
        }


class ProviderHealthMetric(Base):
    """
    Modelo para tabla provider_health_metrics
    Métricas agregadas de salud por proveedor y período
    """
    __tablename__ = "provider_health_metrics"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Referencia al proveedor
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=False, index=True)
    
    # Período de la métrica
    metric_date = Column(DateTime, nullable=False, index=True)
    metric_hour = Column(Integer, nullable=True)
    
    # Contadores de health checks
    total_checks = Column(Integer, default=0, nullable=False)
    successful_checks = Column(Integer, default=0, nullable=False)
    failed_checks = Column(Integer, default=0, nullable=False)
    
    # Métricas de performance
    avg_response_time_ms = Column(Integer, nullable=True)
    min_response_time_ms = Column(Integer, nullable=True)
    max_response_time_ms = Column(Integer, nullable=True)
    p95_response_time_ms = Column(Integer, nullable=True)
    
    # Métricas de disponibilidad
    uptime_percentage = Column(DECIMAL(5, 2), nullable=True)
    downtime_minutes = Column(Integer, default=0, nullable=False)
    
    # Errores e incidentes
    error_count = Column(Integer, default=0, nullable=False)
    incident_count = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    provider = relationship("Provider", back_populates="metrics")

    # Índices compuestos
    __table_args__ = (
        Index("idx_provider_date_hour", "provider_id", "metric_date", "metric_hour", unique=True),
        Index("idx_provider_date", "provider_id", "metric_date"),
    )

    def __repr__(self):
        return f"<ProviderHealthMetric(provider_id={self.provider_id}, metric_date='{self.metric_date}', uptime={self.uptime_percentage}%)>"

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario"""
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "metric_date": self.metric_date.isoformat() if self.metric_date else None,
            "metric_hour": self.metric_hour,
            "total_checks": self.total_checks,
            "successful_checks": self.successful_checks,
            "failed_checks": self.failed_checks,
            "avg_response_time_ms": self.avg_response_time_ms,
            "min_response_time_ms": self.min_response_time_ms,
            "max_response_time_ms": self.max_response_time_ms,
            "p95_response_time_ms": self.p95_response_time_ms,
            "uptime_percentage": float(self.uptime_percentage) if self.uptime_percentage else None,
            "downtime_minutes": self.downtime_minutes,
            "error_count": self.error_count,
            "incident_count": self.incident_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }