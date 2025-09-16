"""
Metrics Models - Modelos Pydantic para responses de métricas
Estructuras de datos para endpoints de estadísticas y métricas
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator


class MetricsPeriod(BaseModel):
    """Período de tiempo para las métricas"""
    start: datetime = Field(..., description="Fecha/hora de inicio del período")
    end: datetime = Field(..., description="Fecha/hora de fin del período")
    hours: Optional[int] = Field(None, description="Número de horas del período")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MetricsFilter(BaseModel):
    """Filtros aplicados a las métricas"""
    provider: Optional[str] = Field(None, description="Proveedor filtrado")
    template_id: Optional[str] = Field(None, description="Template filtrado")
    status: Optional[str] = Field(None, description="Estado filtrado")


class ProviderMetrics(BaseModel):
    """Métricas de un proveedor específico"""
    provider: str = Field(..., description="Nombre del proveedor")
    total_notifications: int = Field(..., description="Total de notificaciones")
    sent_count: int = Field(..., description="Notificaciones enviadas exitosamente")
    failed_count: int = Field(..., description="Notificaciones fallidas")
    rejected_count: int = Field(..., description="Notificaciones rechazadas")
    pending_count: int = Field(..., description="Notificaciones pendientes")
    processing_count: int = Field(..., description="Notificaciones en procesamiento")
    avg_delivery_time_seconds: Optional[float] = Field(None, description="Tiempo promedio de entrega en segundos")
    unique_recipients: Optional[int] = Field(None, description="Destinatarios únicos")
    templates_used: Optional[int] = Field(None, description="Templates utilizados")
    success_rate: float = Field(..., description="Tasa de éxito (%)")
    failure_rate: float = Field(..., description="Tasa de fallos (%)")
    throughput_per_hour: Optional[float] = Field(None, description="Throughput por hora")


class StatusDistribution(BaseModel):
    """Distribución de estados de notificaciones"""
    status: str = Field(..., description="Estado de la notificación")
    count: int = Field(..., description="Cantidad de notificaciones en este estado")
    percentage: float = Field(..., description="Porcentaje del total")


class TimeDistribution(BaseModel):
    """Distribución de tiempos de entrega"""
    time_range: str = Field(..., description="Rango de tiempo (ej: '0-5s', '6-15s')")
    count: int = Field(..., description="Cantidad de notificaciones en este rango")
    percentage: Optional[float] = Field(None, description="Porcentaje del total")


class HourlyTrend(BaseModel):
    """Tendencia por hora"""
    timestamp: str = Field(..., description="Hora (formato: YYYY-MM-DD HH:00:00)")
    total_notifications: int = Field(..., description="Total de notificaciones en esa hora")
    sent_count: int = Field(..., description="Enviadas en esa hora")
    failed_count: int = Field(..., description="Fallidas en esa hora")
    avg_delivery_time: Optional[float] = Field(None, description="Tiempo promedio de entrega")
    success_rate: float = Field(..., description="Tasa de éxito en esa hora")


class TemplatePerformance(BaseModel):
    """Rendimiento de un template"""
    template_id: str = Field(..., description="ID del template")
    template_version: Optional[str] = Field(None, description="Versión del template")
    usage_count: int = Field(..., description="Veces utilizado")
    success_count: int = Field(..., description="Envíos exitosos")
    failure_count: int = Field(..., description="Envíos fallidos")
    avg_delivery_time: Optional[float] = Field(None, description="Tiempo promedio de entrega")
    unique_recipients: int = Field(..., description="Destinatarios únicos")
    first_used: Optional[str] = Field(None, description="Primera vez utilizado")
    last_used: Optional[str] = Field(None, description="Última vez utilizado")
    success_rate: float = Field(..., description="Tasa de éxito del template")
    failure_rate: float = Field(..., description="Tasa de fallos del template")


class ErrorAnalysis(BaseModel):
    """Análisis de error específico"""
    error_message: str = Field(..., description="Mensaje de error")
    occurrence_count: int = Field(..., description="Número de ocurrencias")
    affected_messages: int = Field(..., description="Mensajes afectados")
    provider: Optional[str] = Field(None, description="Proveedor donde ocurrió")
    component: Optional[str] = Field(None, description="Componente donde ocurrió")


class ProviderErrorSummary(BaseModel):
    """Resumen de errores por proveedor"""
    provider: str = Field(..., description="Nombre del proveedor")
    total_errors: int = Field(..., description="Total de errores")
    failed_messages: int = Field(..., description="Mensajes fallidos")
    error_types: List[str] = Field(..., description="Tipos de errores")


class DeliveryMetrics(BaseModel):
    """Métricas de entrega"""
    total_delivered: int = Field(..., description="Total de mensajes entregados")
    avg_delivery_seconds: float = Field(..., description="Tiempo promedio de entrega")
    min_delivery_seconds: float = Field(..., description="Tiempo mínimo de entrega")
    max_delivery_seconds: float = Field(..., description="Tiempo máximo de entrega")
    std_delivery_seconds: Optional[float] = Field(None, description="Desviación estándar")


class ProcessingMetrics(BaseModel):
    """Métricas de procesamiento"""
    total_logged: int = Field(..., description="Total de eventos logueados")
    avg_processing_ms: float = Field(..., description="Tiempo promedio de procesamiento (ms)")
    min_processing_ms: float = Field(..., description="Tiempo mínimo de procesamiento (ms)")
    max_processing_ms: float = Field(..., description="Tiempo máximo de procesamiento (ms)")


class QueueStatus(BaseModel):
    """Estado de una cola específica"""
    count: int = Field(..., description="Cantidad de mensajes en la cola")
    oldest_message: Optional[str] = Field(None, description="Mensaje más antiguo")
    newest_message: Optional[str] = Field(None, description="Mensaje más reciente")


class SystemHealthMetrics(BaseModel):
    """Métricas para calcular salud del sistema"""
    success_rate: float = Field(..., description="Tasa de éxito global")
    failure_rate: float = Field(..., description="Tasa de fallos global")
    stale_pending_rate: float = Field(..., description="Tasa de mensajes pendientes antiguos")
    avg_delivery_time: float = Field(..., description="Tiempo promedio de entrega")
    active_providers: int = Field(..., description="Proveedores activos")
    total_messages: int = Field(..., description="Total de mensajes")


class SystemHealthStatus(str, Enum):
    """Estados de salud del sistema"""
    EXCELLENT = "excellent"
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class SystemHealth(BaseModel):
    """Estado de salud del sistema"""
    health_score: float = Field(..., description="Score de salud (0-100)")
    status: SystemHealthStatus = Field(..., description="Estado de salud")
    metrics: SystemHealthMetrics = Field(..., description="Métricas utilizadas")
    recommendations: List[str] = Field(..., description="Recomendaciones de mejora")


# === RESPONSE MODELS COMPUESTOS ===

class ProviderMetricsResponse(BaseModel):
    """Response para métricas de proveedores"""
    period: MetricsPeriod = Field(..., description="Período consultado")
    summary: Dict[str, Any] = Field(..., description="Resumen general")
    providers: List[ProviderMetrics] = Field(..., description="Métricas por proveedor")


class StatusMetricsResponse(BaseModel):
    """Response para métricas de estado"""
    period: MetricsPeriod = Field(..., description="Período consultado")
    filter: MetricsFilter = Field(..., description="Filtros aplicados")
    summary: Dict[str, int] = Field(..., description="Resumen total")
    status_distribution: List[StatusDistribution] = Field(..., description="Distribución por estado")


class PerformanceMetricsResponse(BaseModel):
    """Response para métricas de rendimiento"""
    period: MetricsPeriod = Field(..., description="Período consultado")
    filter: MetricsFilter = Field(..., description="Filtros aplicados")
    delivery_metrics: DeliveryMetrics = Field(..., description="Métricas de entrega")
    processing_metrics: ProcessingMetrics = Field(..., description="Métricas de procesamiento")
    time_distribution: List[TimeDistribution] = Field(..., description="Distribución de tiempos")


class TrendsResponse(BaseModel):
    """Response para tendencias temporales"""
    period: MetricsPeriod = Field(..., description="Período consultado")
    filter: MetricsFilter = Field(..., description="Filtros aplicados")
    hourly_data: List[HourlyTrend] = Field(..., description="Datos por hora")
    summary: Dict[str, Any] = Field(..., description="Resumen de tendencias")


class TemplateMetricsResponse(BaseModel):
    """Response para métricas de templates"""
    period: MetricsPeriod = Field(..., description="Período consultado")
    filter: MetricsFilter = Field(..., description="Filtros aplicados")
    templates: List[TemplatePerformance] = Field(..., description="Rendimiento por template")
    summary: Dict[str, Any] = Field(..., description="Resumen de templates")


class ErrorAnalysisResponse(BaseModel):
    """Response para análisis de errores"""
    period: MetricsPeriod = Field(..., description="Período consultado")
    filter: MetricsFilter = Field(..., description="Filtros aplicados")
    top_errors: List[ErrorAnalysis] = Field(..., description="Errores más frecuentes")
    provider_errors: List[ProviderErrorSummary] = Field(..., description="Errores por proveedor")
    total_error_types: int = Field(..., description="Total de tipos de error")


class QueueMetricsResponse(BaseModel):
    """Response para métricas de cola"""
    current_queue: Dict[str, QueueStatus] = Field(..., description="Estado actual de colas")
    processing_metrics: ProcessingMetrics = Field(..., description="Métricas de procesamiento")
    queue_health: str = Field(..., description="Estado de salud de las colas")


class MetricsSummaryResponse(BaseModel):
    """Response para resumen general de métricas"""
    period: MetricsPeriod = Field(..., description="Período consultado")
    overview: Dict[str, Any] = Field(..., description="Vista general del sistema")
    system_health: Dict[str, Any] = Field(..., description="Salud del sistema")
    top_templates: List[Dict[str, Any]] = Field(..., description="Templates más utilizados")


class AdvancedMetricsResponse(BaseModel):
    """Response completa con métricas avanzadas"""
    period: MetricsPeriod = Field(..., description="Período consultado")
    filter: MetricsFilter = Field(..., description="Filtros aplicados")
    
    # Métricas principales
    provider_stats: List[ProviderMetrics] = Field(..., description="Estadísticas por proveedor")
    status_distribution: List[StatusDistribution] = Field(..., description="Distribución de estados")
    hourly_trends: List[HourlyTrend] = Field(..., description="Tendencias por hora")
    
    # Métricas de rendimiento
    delivery_performance: DeliveryMetrics = Field(..., description="Rendimiento de entrega")
    processing_performance: ProcessingMetrics = Field(..., description="Rendimiento de procesamiento")
    
    # Análisis de errores
    error_analysis: ErrorAnalysisResponse = Field(..., description="Análisis de errores")
    
    # Estado del sistema
    system_health: SystemHealth = Field(..., description="Estado de salud del sistema")
    
    # Resumen ejecutivo
    executive_summary: Dict[str, Any] = Field(..., description="Resumen ejecutivo")


# === MODELOS PARA FILTROS DE QUERY ===

class MetricsQueryParams(BaseModel):
    """Parámetros de consulta para endpoints de métricas"""
    provider: Optional[str] = Field(None, description="Filtrar por proveedor")
    hours: Optional[int] = Field(24, description="Últimas N horas", ge=1, le=168)  # max 1 semana
    date_from: Optional[str] = Field(None, description="Fecha inicio (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Fecha fin (YYYY-MM-DD)")
    template_id: Optional[str] = Field(None, description="Filtrar por template")
    status: Optional[str] = Field(None, description="Filtrar por estado")
    
    @validator('date_from', 'date_to')
    def validate_date_format(cls, v):
        if v is not None:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Date must be in YYYY-MM-DD format')
        return v
    
    @validator('date_to')
    def validate_date_range(cls, v, values):
        if v is not None and 'date_from' in values and values['date_from'] is not None:
            date_from = datetime.strptime(values['date_from'], '%Y-%m-%d')
            date_to = datetime.strptime(v, '%Y-%m-%d')
            if date_to < date_from:
                raise ValueError('date_to must be after date_from')
        return v


class MetricsExportFormat(str, Enum):
    """Formatos de exportación de métricas"""
    JSON = "json"
    CSV = "csv"
    XLSX = "xlsx"


class MetricsExportRequest(BaseModel):
    """Request para exportar métricas"""
    format: MetricsExportFormat = Field(..., description="Formato de exportación")
    query_params: MetricsQueryParams = Field(..., description="Parámetros de consulta")
    include_charts: bool = Field(False, description="Incluir gráficos (solo para XLSX)")
    filename: Optional[str] = Field(None, description="Nombre del archivo")


# === CONFIGURACIÓN DE MODELOS ===

# Configuración común para todos los modelos
class BaseMetricsModel(BaseModel):
    """Modelo base para métricas con configuración común"""
    
    class Config:
        # Permitir campos extra para flexibilidad futura
        extra = "allow"
        
        # Encoders JSON personalizados
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        
        # Validar tipos de campo
        validate_assignment = True
        
        # Usar enums por valor
        use_enum_values = True
        
        # Permitir mutación para caching
        allow_mutation = True
        
        # Schema extra para documentación
        schema_extra = {
            "example": {
                "timestamp": "2024-01-15T10:30:00",
                "description": "Generated by notify-stack metrics API"
            }
        }


# Aplicar configuración base a modelos principales
ProviderMetrics.Config = BaseMetricsModel.Config
StatusDistribution.Config = BaseMetricsModel.Config
HourlyTrend.Config = BaseMetricsModel.Config
TemplatePerformance.Config = BaseMetricsModel.Config
SystemHealth.Config = BaseMetricsModel.Config


# === VALIDATORS PERSONALIZADOS ===

def validate_positive_number(cls, v, field_name: str):
    """Validator para números positivos"""
    if v is not None and v < 0:
        raise ValueError(f'{field_name} must be positive')
    return v


def validate_percentage(cls, v, field_name: str):
    """Validator para porcentajes (0-100)"""
    if v is not None and (v < 0 or v > 100):
        raise ValueError(f'{field_name} must be between 0 and 100')
    return v


# Aplicar validators a modelos que los necesiten
ProviderMetrics.__validators__['validate_success_rate'] = validator('success_rate', allow_reuse=True)(
    lambda cls, v: validate_percentage(cls, v, 'success_rate')
)

ProviderMetrics.__validators__['validate_failure_rate'] = validator('failure_rate', allow_reuse=True)(
    lambda cls, v: validate_percentage(cls, v, 'failure_rate')
)

StatusDistribution.__validators__['validate_percentage'] = validator('percentage', allow_reuse=True)(
    lambda cls, v: validate_percentage(cls, v, 'percentage')
)


# === FACTORY FUNCTIONS ===

def create_empty_metrics_response() -> MetricsSummaryResponse:
    """Crea una respuesta de métricas vacía para casos sin datos"""
    now = datetime.now()
    period = MetricsPeriod(start=now, end=now, hours=0)
    
    return MetricsSummaryResponse(
        period=period,
        overview={
            "total_notifications": 0,
            "sent_count": 0,
            "failed_count": 0,
            "success_rate": 0.0,
            "message": "No data available for selected period"
        },
        system_health={
            "status": "unknown",
            "message": "Insufficient data to determine system health"
        },
        top_templates=[]
    )


def create_metrics_period(hours: Optional[int] = None, 
                         date_from: Optional[str] = None, 
                         date_to: Optional[str] = None) -> MetricsPeriod:
    """Crea un objeto MetricsPeriod desde parámetros de consulta"""
    if date_from and date_to:
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d")
        return MetricsPeriod(start=start, end=end)
    else:
        hours = hours or 24
        end = datetime.now()
        start = end - timedelta(hours=hours)
        return MetricsPeriod(start=start, end=end, hours=hours)