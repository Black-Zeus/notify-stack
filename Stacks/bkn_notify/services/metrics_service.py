"""
Metrics Service - Lógica de negocio para consultas de métricas
Capa de abstracción para consultas complejas de estadísticas
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import text, desc, and_, or_, func
from sqlalchemy.exc import SQLAlchemyError

from utils.database import get_db_session

logger = logging.getLogger(__name__)


@dataclass
class TimeRange:
    """Clase para manejar rangos de tiempo"""
    start: datetime
    end: datetime
    hours: Optional[int] = None
    
    @classmethod
    def from_hours(cls, hours: int) -> 'TimeRange':
        end = datetime.now()
        start = end - timedelta(hours=hours)
        return cls(start=start, end=end, hours=hours)
    
    @classmethod
    def from_dates(cls, date_from: str, date_to: str) -> 'TimeRange':
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        return cls(start=start, end=end)


@dataclass
class MetricsFilter:
    """Clase para filtros de métricas"""
    time_range: TimeRange
    provider: Optional[str] = None
    template_id: Optional[str] = None
    status: Optional[str] = None


class MetricsService:
    """Servicio para consultas de métricas y estadísticas"""

    @staticmethod
    def get_provider_stats(filters: MetricsFilter) -> List[Dict[str, Any]]:
        """
        Obtiene estadísticas agregadas por proveedor
        
        Args:
            filters: Filtros para la consulta
            
        Returns:
            Lista de estadísticas por proveedor
        """
        try:
            with get_db_session() as db:
                query = text("""
                    SELECT 
                        COALESCE(provider, 'unknown') as provider,
                        COUNT(*) as total_notifications,
                        SUM(CASE WHEN status = 'SENT' THEN 1 ELSE 0 END) as sent_count,
                        SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_count,
                        SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected_count,
                        SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending_count,
                        SUM(CASE WHEN status = 'PROCESSING' THEN 1 ELSE 0 END) as processing_count,
                        ROUND(AVG(CASE WHEN status = 'SENT' AND sent_at IS NOT NULL THEN 
                            TIMESTAMPDIFF(SECOND, created_at, sent_at) ELSE NULL END), 2) as avg_delivery_time_seconds,
                        COUNT(DISTINCT to_email) as unique_recipients,
                        COUNT(DISTINCT template_id) as templates_used
                    FROM notifications 
                    WHERE created_at >= :start_date AND created_at < :end_date
                    """ + (" AND provider = :provider" if filters.provider else "") + """
                    GROUP BY provider 
                    ORDER BY sent_count DESC
                """)
                
                params = {
                    'start_date': filters.time_range.start,
                    'end_date': filters.time_range.end
                }
                
                if filters.provider:
                    params['provider'] = filters.provider
                
                result = db.execute(query, params).fetchall()
                
                providers_data = []
                for row in result:
                    provider_stats = {
                        "provider": row[0],
                        "total_notifications": row[1],
                        "sent_count": row[2],
                        "failed_count": row[3],
                        "rejected_count": row[4],
                        "pending_count": row[5],
                        "processing_count": row[6],
                        "avg_delivery_time_seconds": row[7],
                        "unique_recipients": row[8],
                        "templates_used": row[9],
                        "success_rate": round((row[2] / row[1]) * 100, 2) if row[1] > 0 else 0.0,
                        "failure_rate": round((row[3] / row[1]) * 100, 2) if row[1] > 0 else 0.0,
                        "throughput_per_hour": round(row[1] / (filters.time_range.hours or 24), 2)
                    }
                    providers_data.append(provider_stats)
                
                return providers_data
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting provider stats: {str(e)}")
            raise


    @staticmethod
    def get_hourly_trends(filters: MetricsFilter) -> List[Dict[str, Any]]:
        """
        Obtiene tendencias por hora para gráficos temporales
        
        Args:
            filters: Filtros para la consulta
            
        Returns:
            Lista de datos por hora
        """
        try:
            with get_db_session() as db:
                query = text("""
                    SELECT 
                        DATE_FORMAT(created_at, '%Y-%m-%d %H:00:00') as hour_bucket,
                        COUNT(*) as total_notifications,
                        SUM(CASE WHEN status = 'SENT' THEN 1 ELSE 0 END) as sent_count,
                        SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_count,
                        ROUND(AVG(CASE WHEN status = 'SENT' AND sent_at IS NOT NULL THEN 
                            TIMESTAMPDIFF(SECOND, created_at, sent_at) ELSE NULL END), 2) as avg_delivery_time
                    FROM notifications 
                    WHERE created_at >= :start_date AND created_at < :end_date
                    """ + (" AND provider = :provider" if filters.provider else "") + """
                    GROUP BY hour_bucket 
                    ORDER BY hour_bucket
                """)
                
                params = {
                    'start_date': filters.time_range.start,
                    'end_date': filters.time_range.end
                }
                
                if filters.provider:
                    params['provider'] = filters.provider
                
                result = db.execute(query, params).fetchall()
                
                hourly_data = []
                for row in result:
                    hourly_stats = {
                        "timestamp": row[0],
                        "total_notifications": row[1],
                        "sent_count": row[2],
                        "failed_count": row[3],
                        "avg_delivery_time": row[4],
                        "success_rate": round((row[2] / row[1]) * 100, 2) if row[1] > 0 else 0.0
                    }
                    hourly_data.append(hourly_stats)
                
                return hourly_data
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting hourly trends: {str(e)}")
            raise


    @staticmethod
    def get_template_performance(filters: MetricsFilter) -> List[Dict[str, Any]]:
        """
        Obtiene métricas de rendimiento por template
        
        Args:
            filters: Filtros para la consulta
            
        Returns:
            Lista de estadísticas por template
        """
        try:
            with get_db_session() as db:
                query = text("""
                    SELECT 
                        template_id,
                        template_version,
                        COUNT(*) as usage_count,
                        SUM(CASE WHEN status = 'SENT' THEN 1 ELSE 0 END) as success_count,
                        SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failure_count,
                        ROUND(AVG(CASE WHEN status = 'SENT' AND sent_at IS NOT NULL THEN 
                            TIMESTAMPDIFF(SECOND, created_at, sent_at) ELSE NULL END), 2) as avg_delivery_time,
                        COUNT(DISTINCT to_email) as unique_recipients,
                        MIN(created_at) as first_used,
                        MAX(created_at) as last_used
                    FROM notifications 
                    WHERE created_at >= :start_date AND created_at < :end_date
                    AND template_id IS NOT NULL
                    """ + (" AND provider = :provider" if filters.provider else "") + """
                    """ + (" AND template_id = :template_id" if filters.template_id else "") + """
                    GROUP BY template_id, template_version 
                    ORDER BY usage_count DESC
                """)
                
                params = {
                    'start_date': filters.time_range.start,
                    'end_date': filters.time_range.end
                }
                
                if filters.provider:
                    params['provider'] = filters.provider
                if filters.template_id:
                    params['template_id'] = filters.template_id
                
                result = db.execute(query, params).fetchall()
                
                template_data = []
                for row in result:
                    template_stats = {
                        "template_id": row[0],
                        "template_version": row[1],
                        "usage_count": row[2],
                        "success_count": row[3],
                        "failure_count": row[4],
                        "avg_delivery_time": row[5],
                        "unique_recipients": row[6],
                        "first_used": row[7].isoformat() if row[7] else None,
                        "last_used": row[8].isoformat() if row[8] else None,
                        "success_rate": round((row[3] / row[2]) * 100, 2) if row[2] > 0 else 0.0,
                        "failure_rate": round((row[4] / row[2]) * 100, 2) if row[2] > 0 else 0.0
                    }
                    template_data.append(template_stats)
                
                return template_data
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting template performance: {str(e)}")
            raise


    @staticmethod
    def get_delivery_time_distribution(filters: MetricsFilter) -> Dict[str, Any]:
        """
        Obtiene distribución de tiempos de entrega en buckets
        
        Args:
            filters: Filtros para la consulta
            
        Returns:
            Distribución de tiempos por rangos
        """
        try:
            with get_db_session() as db:
                query = text("""
                    SELECT 
                        CASE 
                            WHEN TIMESTAMPDIFF(SECOND, created_at, sent_at) <= 5 THEN '0-5s'
                            WHEN TIMESTAMPDIFF(SECOND, created_at, sent_at) <= 15 THEN '6-15s'
                            WHEN TIMESTAMPDIFF(SECOND, created_at, sent_at) <= 30 THEN '16-30s'
                            WHEN TIMESTAMPDIFF(SECOND, created_at, sent_at) <= 60 THEN '31-60s'
                            WHEN TIMESTAMPDIFF(SECOND, created_at, sent_at) <= 300 THEN '1-5min'
                            ELSE '>5min'
                        END as time_bucket,
                        COUNT(*) as count,
                        ROUND((COUNT(*) * 100.0) / SUM(COUNT(*)) OVER(), 2) as percentage
                    FROM notifications 
                    WHERE created_at >= :start_date AND created_at < :end_date
                    AND status = 'SENT' AND sent_at IS NOT NULL
                    """ + (" AND provider = :provider" if filters.provider else "") + """
                    GROUP BY time_bucket 
                    ORDER BY FIELD(time_bucket, '0-5s', '6-15s', '16-30s', '31-60s', '1-5min', '>5min')
                """)
                
                params = {
                    'start_date': filters.time_range.start,
                    'end_date': filters.time_range.end
                }
                
                if filters.provider:
                    params['provider'] = filters.provider
                
                result = db.execute(query, params).fetchall()
                
                distribution = []
                total_messages = 0
                
                for row in result:
                    bucket_data = {
                        "time_range": row[0],
                        "count": row[1],
                        "percentage": row[2]
                    }
                    distribution.append(bucket_data)
                    total_messages += row[1]
                
                return {
                    "total_delivered": total_messages,
                    "distribution": distribution
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting delivery time distribution: {str(e)}")
            raise


    @staticmethod
    def get_error_analysis(filters: MetricsFilter) -> Dict[str, Any]:
        """
        Obtiene análisis detallado de errores desde logs
        
        Args:
            filters: Filtros para la consulta
            
        Returns:
            Análisis de errores y fallos
        """
        try:
            with get_db_session() as db:
                # Top errores por mensaje
                error_query = text("""
                    SELECT 
                        event_message,
                        COUNT(*) as occurrence_count,
                        COUNT(DISTINCT message_id) as affected_messages,
                        provider,
                        component
                    FROM notification_logs 
                    WHERE timestamp >= :start_date AND timestamp < :end_date
                    AND event_type IN ('ERROR', 'FAILED', 'REJECTED')
                    """ + (" AND provider = :provider" if filters.provider else "") + """
                    GROUP BY event_message, provider, component
                    ORDER BY occurrence_count DESC
                    LIMIT 10
                """)
                
                # Distribución de errores por proveedor
                provider_error_query = text("""
                    SELECT 
                        provider,
                        COUNT(*) as total_errors,
                        COUNT(DISTINCT message_id) as failed_messages,
                        GROUP_CONCAT(DISTINCT event_type) as error_types
                    FROM notification_logs 
                    WHERE timestamp >= :start_date AND timestamp < :end_date
                    AND event_type IN ('ERROR', 'FAILED', 'REJECTED')
                    """ + (" AND provider = :provider" if filters.provider else "") + """
                    GROUP BY provider
                    ORDER BY total_errors DESC
                """)
                
                params = {
                    'start_date': filters.time_range.start,
                    'end_date': filters.time_range.end
                }
                
                if filters.provider:
                    params['provider'] = filters.provider
                
                # Ejecutar consultas
                error_result = db.execute(error_query, params).fetchall()
                provider_error_result = db.execute(provider_error_query, params).fetchall()
                
                # Procesar top errores
                top_errors = []
                for row in error_result:
                    error_info = {
                        "error_message": row[0],
                        "occurrence_count": row[1],
                        "affected_messages": row[2],
                        "provider": row[3],
                        "component": row[4]
                    }
                    top_errors.append(error_info)
                
                # Procesar errores por proveedor
                provider_errors = []
                for row in provider_error_result:
                    provider_error_info = {
                        "provider": row[0],
                        "total_errors": row[1],
                        "failed_messages": row[2],
                        "error_types": row[3].split(',') if row[3] else []
                    }
                    provider_errors.append(provider_error_info)
                
                return {
                    "top_errors": top_errors,
                    "provider_errors": provider_errors,
                    "total_error_types": len(set([err["component"] for err in top_errors if err["component"]]))
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting error analysis: {str(e)}")
            raise


    @staticmethod
    def get_queue_metrics(filters: MetricsFilter) -> Dict[str, Any]:
        """
        Obtiene métricas relacionadas con colas y procesamiento
        
        Args:
            filters: Filtros para la consulta
            
        Returns:
            Métricas de cola y procesamiento
        """
        try:
            with get_db_session() as db:
                # Métricas de estado actual
                current_queue_query = text("""
                    SELECT 
                        status,
                        COUNT(*) as count,
                        MIN(created_at) as oldest_message,
                        MAX(created_at) as newest_message
                    FROM notifications 
                    WHERE status IN ('PENDING', 'PROCESSING')
                    """ + (" AND provider = :provider" if filters.provider else "") + """
                    GROUP BY status
                """)
                
                # Métricas de procesamiento por hora en el período
                processing_time_query = text("""
                    SELECT 
                        AVG(processing_time_ms) as avg_processing_ms,
                        MIN(processing_time_ms) as min_processing_ms,
                        MAX(processing_time_ms) as max_processing_ms,
                        STDDEV(processing_time_ms) as std_processing_ms,
                        COUNT(*) as total_processed
                    FROM notification_logs 
                    WHERE timestamp >= :start_date AND timestamp < :end_date
                    AND processing_time_ms IS NOT NULL
                    """ + (" AND provider = :provider" if filters.provider else "") + """
                """)
                
                params = {
                    'start_date': filters.time_range.start,
                    'end_date': filters.time_range.end
                }
                
                if filters.provider:
                    params['provider'] = filters.provider
                
                # Ejecutar consultas
                queue_result = db.execute(current_queue_query, params).fetchall()
                processing_result = db.execute(processing_time_query, params).fetchone()
                
                # Procesar cola actual
                current_queue = {}
                for row in queue_result:
                    current_queue[row[0].lower()] = {
                        "count": row[1],
                        "oldest_message": row[2].isoformat() if row[2] else None,
                        "newest_message": row[3].isoformat() if row[3] else None
                    }
                
                # Procesar métricas de tiempo
                processing_metrics = {
                    "avg_processing_ms": round(processing_result[0], 2) if processing_result[0] else 0,
                    "min_processing_ms": processing_result[1] if processing_result[1] else 0,
                    "max_processing_ms": processing_result[2] if processing_result[2] else 0,
                    "std_processing_ms": round(processing_result[3], 2) if processing_result[3] else 0,
                    "total_processed": processing_result[4] if processing_result[4] else 0
                }
                
                return {
                    "current_queue": current_queue,
                    "processing_metrics": processing_metrics,
                    "queue_health": "healthy" if current_queue.get("pending", {}).get("count", 0) < 100 else "warning"
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting queue metrics: {str(e)}")
            raise


    @staticmethod
    def calculate_system_health_score(filters: MetricsFilter) -> Dict[str, Any]:
        """
        Calcula un score de salud del sistema basado en múltiples métricas
        
        Args:
            filters: Filtros para la consulta
            
        Returns:
            Score de salud y detalles
        """
        try:
            with get_db_session() as db:
                health_query = text("""
                    SELECT 
                        COUNT(*) as total_messages,
                        SUM(CASE WHEN status = 'SENT' THEN 1 ELSE 0 END) as success_count,
                        SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failure_count,
                        SUM(CASE WHEN status = 'PENDING' AND created_at < DATE_SUB(NOW(), INTERVAL 1 HOUR) THEN 1 ELSE 0 END) as stale_pending,
                        AVG(CASE WHEN status = 'SENT' AND sent_at IS NOT NULL THEN 
                            TIMESTAMPDIFF(SECOND, created_at, sent_at) ELSE NULL END) as avg_delivery_time,
                        COUNT(DISTINCT provider) as active_providers
                    FROM notifications 
                    WHERE created_at >= :start_date AND created_at < :end_date
                """)
                
                params = {
                    'start_date': filters.time_range.start,
                    'end_date': filters.time_range.end
                }
                
                result = db.execute(health_query, params).fetchone()
                
                if not result or result[0] == 0:
                    return {
                        "health_score": 100,
                        "status": "healthy",
                        "details": "No activity in selected period"
                    }
                
                total = result[0]
                success_count = result[1]
                failure_count = result[2]
                stale_pending = result[3]
                avg_delivery = result[4] or 0
                active_providers = result[5]
                
                # Calcular componentes del score
                success_rate = (success_count / total) * 100 if total > 0 else 0
                failure_rate = (failure_count / total) * 100 if total > 0 else 0
                stale_rate = (stale_pending / total) * 100 if total > 0 else 0
                
                # Score de salud (0-100)
                health_score = 100
                
                # Penalizar por failure rate
                if failure_rate > 20:
                    health_score -= 40
                elif failure_rate > 10:
                    health_score -= 25
                elif failure_rate > 5:
                    health_score -= 15
                
                # Penalizar por mensajes pendientes antiguos
                if stale_rate > 10:
                    health_score -= 30
                elif stale_rate > 5:
                    health_score -= 15
                
                # Penalizar por delivery time lento
                if avg_delivery > 300:  # > 5 minutos
                    health_score -= 20
                elif avg_delivery > 60:  # > 1 minuto
                    health_score -= 10
                
                # Bonificar por múltiples proveedores activos
                if active_providers > 1:
                    health_score += 5
                
                # Limitar entre 0 y 100
                health_score = max(0, min(100, health_score))
                
                # Determinar status
                if health_score >= 90:
                    status = "excellent"
                elif health_score >= 75:
                    status = "healthy"
                elif health_score >= 50:
                    status = "warning"
                else:
                    status = "critical"
                
                return {
                    "health_score": round(health_score, 1),
                    "status": status,
                    "metrics": {
                        "success_rate": round(success_rate, 2),
                        "failure_rate": round(failure_rate, 2),
                        "stale_pending_rate": round(stale_rate, 2),
                        "avg_delivery_time": round(avg_delivery, 2),
                        "active_providers": active_providers,
                        "total_messages": total
                    },
                    "recommendations": MetricsService._get_health_recommendations(
                        failure_rate, stale_rate, avg_delivery, active_providers
                    )
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error calculating health score: {str(e)}")
            raise


    @staticmethod
    def _get_health_recommendations(failure_rate: float, stale_rate: float, 
                                  avg_delivery: float, active_providers: int) -> List[str]:
        """Genera recomendaciones basadas en métricas de salud"""
        recommendations = []
        
        if failure_rate > 10:
            recommendations.append("High failure rate detected. Check provider configurations and logs.")
        
        if stale_rate > 5:
            recommendations.append("Many pending messages detected. Check Celery worker status.")
        
        if avg_delivery > 300:
            recommendations.append("Slow delivery times. Consider scaling workers or optimizing providers.")
        
        if active_providers <= 1:
            recommendations.append("Single provider dependency. Consider adding backup providers.")
        
        if not recommendations:
            recommendations.append("System operating normally. No immediate actions required.")
        
        return recommendations