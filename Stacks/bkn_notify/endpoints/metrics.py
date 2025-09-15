"""
Metrics API Endpoints
Endpoints para consultar métricas y estadísticas desde la base de datos
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse

from sqlalchemy import text

# Importar autenticación con fallback
try:
    from utils.auth import verify_api_key
except ImportError:
    # Fallback si no existe utils.auth
    from fastapi import Depends, HTTPException, Security
    from fastapi.security import APIKeyHeader
    import os
    
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
    
    async def verify_api_key(api_key: str = Security(api_key_header)):
        if not api_key:
            raise HTTPException(status_code=401, detail="X-API-Key header required")
        
        # Verificar contra las claves en variables de entorno
        valid_keys = os.getenv("API_KEYS", "").split(",")
        valid_keys = [key.strip() for key in valid_keys if key.strip()]
        
        if not valid_keys or api_key not in valid_keys:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        return api_key
from services.database_service import DatabaseService
from models.status_response import MetricsResponse
from utils.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/metrics/providers", response_model=Dict[str, Any])
async def get_provider_metrics(
    provider: Optional[str] = Query(None, description="Filtrar por proveedor específico"),
    hours: Optional[int] = Query(24, description="Últimas N horas (default: 24)"),
    date_from: Optional[str] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Fecha fin (YYYY-MM-DD)")
):
    """
    Métricas agregadas por proveedor de email
    
    Retorna estadísticas de envíos, fallos y tiempos por proveedor
    """
    try:
        # Calcular rango temporal
        if date_from and date_to:
            start_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=hours)
        
        with get_db_session() as db:
            
            
            # Query base con filtros
            query = text("""
            SELECT 
                provider,
                COUNT(*) as total_notifications,
                SUM(CASE WHEN status = 'SENT' THEN 1 ELSE 0 END) as sent_count,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_count,
                SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected_count,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN status = 'PROCESSING' THEN 1 ELSE 0 END) as processing_count,
                ROUND(AVG(CASE WHEN status = 'SENT' AND sent_at IS NOT NULL THEN 
                    TIMESTAMPDIFF(SECOND, created_at, sent_at) ELSE NULL END), 2) as avg_delivery_time_seconds
            FROM notifications 
            WHERE created_at >= :start_date AND created_at < :end_date
            """ + (" AND provider = :provider" if provider else "") + """
            GROUP BY provider ORDER BY sent_count DESC
            """)
            
            params = {
                'start_date': start_date,
                'end_date': end_date
            }
            
            if provider:
                params['provider'] = provider
            
            result = db.execute(query, params).fetchall()
            
            # Procesar resultados
            providers_data = []
            total_sent = 0
            total_failed = 0
            total_notifications = 0
            
            for row in result:
                provider_stats = {
                    "provider": row[0] or "unknown",
                    "total_notifications": row[1],
                    "sent_count": row[2],
                    "failed_count": row[3], 
                    "rejected_count": row[4],
                    "pending_count": row[5],
                    "processing_count": row[6],
                    "avg_delivery_time_seconds": row[7],
                    "success_rate": round((row[2] / row[1]) * 100, 2) if row[1] > 0 else 0.0,
                    "failure_rate": round((row[3] / row[1]) * 100, 2) if row[1] > 0 else 0.0
                }
                providers_data.append(provider_stats)
                
                total_sent += row[2]
                total_failed += row[3]
                total_notifications += row[1]
            
            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "hours": hours if not (date_from and date_to) else None
                },
                "summary": {
                    "total_notifications": total_notifications,
                    "total_sent": total_sent,
                    "total_failed": total_failed,
                    "overall_success_rate": round((total_sent / total_notifications) * 100, 2) if total_notifications > 0 else 0.0,
                    "providers_count": len(providers_data)
                },
                "providers": providers_data
            }
            
    except Exception as e:
        logger.error(f"Error getting provider metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving provider metrics: {str(e)}")


@router.get("/metrics/status", response_model=Dict[str, Any])
async def get_status_metrics(
    hours: Optional[int] = Query(24, description="Últimas N horas (default: 24)"),
    provider: Optional[str] = Query(None, description="Filtrar por proveedor")
):
    """
    Distribución de estados de notificaciones
    
    Retorna conteo y porcentajes por cada estado
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)
        
        with get_db_session() as db:
            
            
            query = text("""
            SELECT 
                status,
                COUNT(*) as count,
                ROUND((COUNT(*) * 100.0) / SUM(COUNT(*)) OVER(), 2) as percentage
            FROM notifications 
            WHERE created_at >= :start_date AND created_at < :end_date
            """ + (" AND provider = :provider" if provider else "") + """
            GROUP BY status ORDER BY count DESC
            """)
            
            params = {
                'start_date': start_date,
                'end_date': end_date
            }
            
            if provider:
                params['provider'] = provider
                
            result = db.execute(query, params).fetchall()
            
            status_data = []
            total_count = 0
            
            for row in result:
                status_info = {
                    "status": row[0],
                    "count": row[1],
                    "percentage": row[2]
                }
                status_data.append(status_info)
                total_count += row[1]
            
            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "hours": hours
                },
                "filter": {
                    "provider": provider
                },
                "summary": {
                    "total_notifications": total_count
                },
                "status_distribution": status_data
            }
            
    except Exception as e:
        logger.error(f"Error getting status metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving status metrics: {str(e)}")


@router.get("/metrics/performance", response_model=Dict[str, Any]) 
async def get_performance_metrics(
    hours: Optional[int] = Query(24, description="Últimas N horas (default: 24)"),
    provider: Optional[str] = Query(None, description="Filtrar por proveedor")
):
    """
    Métricas de rendimiento y tiempos de procesamiento
    
    Retorna estadísticas de tiempos de delivery y procesamiento
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)
        
        with get_db_session() as db:
            
            
            # Query para métricas de delivery time
            delivery_query = text("""
            SELECT 
                COUNT(*) as total_delivered,
                ROUND(AVG(TIMESTAMPDIFF(SECOND, created_at, sent_at)), 2) as avg_delivery_seconds,
                ROUND(MIN(TIMESTAMPDIFF(SECOND, created_at, sent_at)), 2) as min_delivery_seconds,
                ROUND(MAX(TIMESTAMPDIFF(SECOND, created_at, sent_at)), 2) as max_delivery_seconds,
                ROUND(STDDEV(TIMESTAMPDIFF(SECOND, created_at, sent_at)), 2) as std_delivery_seconds
            FROM notifications 
            WHERE created_at >= :start_date AND created_at < :end_date 
            AND status = 'SENT' AND sent_at IS NOT NULL
            """ + (" AND provider = :provider" if provider else ""))
            
            params = {
                'start_date': start_date,
                'end_date': end_date
            }
            
            if provider:
                params['provider'] = provider
            
            delivery_result = db.execute(delivery_query, params).fetchone()
            
            # Query para métricas de processing time de logs
            processing_query = text("""
            SELECT 
                COUNT(*) as total_logged,
                ROUND(AVG(processing_time_ms), 2) as avg_processing_ms,
                ROUND(MIN(processing_time_ms), 2) as min_processing_ms,
                ROUND(MAX(processing_time_ms), 2) as max_processing_ms
            FROM notification_logs 
            WHERE timestamp >= :start_date AND timestamp < :end_date 
            AND processing_time_ms IS NOT NULL
            """ + (" AND provider = :provider" if provider else ""))
            
            processing_result = db.execute(processing_query, params).fetchone()
            
            # Query para distribución de tiempos por rangos
            time_distribution_query = text("""
            SELECT 
                CASE 
                    WHEN TIMESTAMPDIFF(SECOND, created_at, sent_at) <= 5 THEN '0-5s'
                    WHEN TIMESTAMPDIFF(SECOND, created_at, sent_at) <= 15 THEN '6-15s'
                    WHEN TIMESTAMPDIFF(SECOND, created_at, sent_at) <= 30 THEN '16-30s'
                    WHEN TIMESTAMPDIFF(SECOND, created_at, sent_at) <= 60 THEN '31-60s'
                    ELSE '>60s'
                END as time_range,
                COUNT(*) as count
            FROM notifications 
            WHERE created_at >= :start_date AND created_at < :end_date 
            AND status = 'SENT' AND sent_at IS NOT NULL
            """ + (" AND provider = :provider" if provider else "") + """
            GROUP BY time_range ORDER BY FIELD(time_range, '0-5s', '6-15s', '16-30s', '31-60s', '>60s')
            """)
            
            time_dist_result = db.execute(time_distribution_query, params).fetchall()
            
            # Procesar distribución de tiempos
            time_distribution = []
            for row in time_dist_result:
                time_distribution.append({
                    "range": row[0],
                    "count": row[1]
                })
            
            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "hours": hours
                },
                "filter": {
                    "provider": provider
                },
                "delivery_metrics": {
                    "total_delivered": delivery_result[0] if delivery_result[0] else 0,
                    "avg_delivery_seconds": delivery_result[1] if delivery_result[1] else 0,
                    "min_delivery_seconds": delivery_result[2] if delivery_result[2] else 0,
                    "max_delivery_seconds": delivery_result[3] if delivery_result[3] else 0,
                    "std_delivery_seconds": delivery_result[4] if delivery_result[4] else 0
                },
                "processing_metrics": {
                    "total_logged": processing_result[0] if processing_result[0] else 0,
                    "avg_processing_ms": processing_result[1] if processing_result[1] else 0,
                    "min_processing_ms": processing_result[2] if processing_result[2] else 0,
                    "max_processing_ms": processing_result[3] if processing_result[3] else 0
                },
                "time_distribution": time_distribution
            }
            
    except Exception as e:
        logger.error(f"Error getting performance metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving performance metrics: {str(e)}")


@router.get("/metrics/summary", response_model=Dict[str, Any])
async def get_metrics_summary(
    hours: Optional[int] = Query(24, description="Últimas N horas (default: 24)")
):
    """
    Resumen general de métricas del sistema
    
    Retorna un dashboard completo con las métricas más importantes
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)
        
        with get_db_session() as db:
            from sqlalchemy import text
            
            # Query principal para resumen
            summary_query = text("""
            SELECT 
                COUNT(*) as total_notifications,
                SUM(CASE WHEN status = 'SENT' THEN 1 ELSE 0 END) as sent_count,
                SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_count,
                SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected_count,
                SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN status = 'PROCESSING' THEN 1 ELSE 0 END) as processing_count,
                COUNT(DISTINCT provider) as active_providers,
                COUNT(DISTINCT template_id) as templates_used,
                ROUND(AVG(CASE WHEN status = 'SENT' AND sent_at IS NOT NULL THEN 
                    TIMESTAMPDIFF(SECOND, created_at, sent_at) ELSE NULL END), 2) as avg_delivery_time
            FROM notifications 
            WHERE created_at >= :start_date AND created_at < :end_date
            """)
            
            result = db.execute(summary_query, {'start_date': start_date, 'end_date': end_date}).fetchone()
            
            # Query para top templates
            templates_query = text("""
            SELECT 
                template_id,
                COUNT(*) as usage_count,
                SUM(CASE WHEN status = 'SENT' THEN 1 ELSE 0 END) as success_count
            FROM notifications 
            WHERE created_at >= :start_date AND created_at < :end_date AND template_id IS NOT NULL
            GROUP BY template_id 
            ORDER BY usage_count DESC 
            LIMIT 5
            """)
            
            templates_result = db.execute(templates_query, {'start_date': start_date, 'end_date': end_date}).fetchall()
            
            # Procesar top templates
            top_templates = []
            for row in templates_result:
                top_templates.append({
                    "template_id": row[0],
                    "usage_count": row[1],
                    "success_count": row[2],
                    "success_rate": round((row[2] / row[1]) * 100, 2) if row[1] > 0 else 0.0
                })
            
            # Calcular tasas y ratios
            total = result[0] if result[0] else 0
            sent = result[1] if result[1] else 0
            failed = result[2] if result[2] else 0
            
            success_rate = round((sent / total) * 100, 2) if total > 0 else 0.0
            failure_rate = round((failed / total) * 100, 2) if total > 0 else 0.0
            
            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "hours": hours
                },
                "overview": {
                    "total_notifications": total,
                    "sent_count": sent,
                    "failed_count": failed,
                    "rejected_count": result[3] if result[3] else 0,
                    "pending_count": result[4] if result[4] else 0,
                    "processing_count": result[5] if result[5] else 0,
                    "success_rate": success_rate,
                    "failure_rate": failure_rate,
                    "avg_delivery_time_seconds": result[8] if result[8] else 0
                },
                "system_health": {
                    "active_providers": result[6] if result[6] else 0,
                    "templates_used": result[7] if result[7] else 0,
                    "system_status": "healthy" if failure_rate < 5.0 else "warning" if failure_rate < 15.0 else "critical"
                },
                "top_templates": top_templates
            }
            
    except Exception as e:
        logger.error(f"Error getting metrics summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving metrics summary: {str(e)}")

@router.get("/metrics/health")
async def metrics_health():
    """Health check específico para el módulo de métricas"""
    try:
        with get_db_session() as db:
            # Test simple query
            result = db.execute(text("SELECT COUNT(*) FROM notifications")).fetchone()
            
            return {
                "status": "healthy",
                "database": "connected",
                "timestamp": datetime.now().isoformat(),
                "total_notifications": result[0] if result else 0
            }
    except Exception as e:
        logger.error(f"Metrics health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected", 
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )