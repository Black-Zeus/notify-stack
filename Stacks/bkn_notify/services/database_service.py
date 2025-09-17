"""
Stacks/bkn_notify/services/database_service.py
Database Service - Operaciones CRUD para notificaciones
Capa de abstracción para operaciones de base de datos
"""

import logging
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
from sqlalchemy.exc import SQLAlchemyError

from models.database_models import (
    Notification, NotificationLog, NotificationAttachment, 
    ProviderStats, NotificationStatus, NotificationPriority,
    get_priority_from_string  # ✅ AGREGADO: Import de la función helper
)
from utils.database import get_db_session

logger = logging.getLogger(__name__)


class DatabaseService:
    """Servicio para operaciones de base de datos"""

    @staticmethod
    def create_notification(
        message_id: str,
        to_email: str,
        subject: Optional[str] = None,
        template_id: Optional[str] = None,
        params_json: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        celery_task_id: Optional[str] = None,
        priority: Optional[str] = None,  # Agregado para manejar priority
        **kwargs
    ) -> Optional[Notification]:
        """Crea una nueva notificación en la base de datos"""
        
        try:
            with get_db_session() as db:
                # ✅ CORREGIDO: Usar la función helper que maneja correctamente el enum
                priority_enum = get_priority_from_string(priority)
                
                logger.info(f"Started notification registration: {message_id}")
                
                notification = Notification(
                    message_id=message_id,
                    to_email=to_email,
                    subject=subject,
                    template_id=template_id,
                    params_json=params_json,
                    provider=provider,
                    celery_task_id=celery_task_id,
                    priority=priority_enum,
                    **kwargs
                )
                
                db.add(notification)
                db.commit()
                db.refresh(notification)
                
                logger.info(f"Created notification: {message_id}")
                logger.info(notification)
                return notification
                
        except SQLAlchemyError as e:
            logger.error(f"Error creating notification {message_id}: {e}")
            return None

    @staticmethod
    def get_notification(message_id: str) -> Optional[Notification]:
        """Obtiene una notificación por message_id"""
        
        try:
            with get_db_session() as db:
                return db.query(Notification).filter(
                    Notification.message_id == message_id
                ).first()
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting notification {message_id}: {e}")
            return None

    @staticmethod
    def update_notification_status(
        message_id: str, 
        status: NotificationStatus,
        sent_at: Optional[datetime] = None,
        retry_count: Optional[int] = None,
        celery_task_id: Optional[str] = None,  # ✅ AGREGADO: Parámetro faltante
        provider_response: Optional[Dict[str, Any]] = None,  # ✅ AGREGADO: Para respuestas del proveedor
        error_message: Optional[str] = None  # ✅ AGREGADO: Para mensajes de error
    ) -> bool:
        """Actualiza el estado de una notificación"""
        
        try:
            with get_db_session() as db:
                notification = db.query(Notification).filter(
                    Notification.message_id == message_id
                ).first()
                
                if not notification:
                    logger.warning(f"Notification not found: {message_id}")
                    return False
                
                # Actualizar campos básicos
                notification.status = status
                if sent_at:
                    notification.sent_at = sent_at
                if retry_count is not None:
                    notification.retry_count = retry_count
                if celery_task_id:
                    notification.celery_task_id = celery_task_id
                
                # Actualizar timestamp
                notification.updated_at = datetime.utcnow()
                
                db.commit()
                logger.debug(f"Updated notification {message_id} to {status}")
                
                # Log del cambio de estado si hay información adicional
                if provider_response or error_message:
                    details = {}
                    if provider_response:
                        details["provider_response"] = provider_response
                    if error_message:
                        details["error_message"] = error_message
                    
                    DatabaseService.add_notification_log(
                        message_id=message_id,
                        event_type="status_updated",
                        event_status=status.value,
                        event_message=f"Status updated to {status.value}",
                        details_json=details,
                        component="database"
                    )
                
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error updating notification {message_id}: {e}")
            return False

    @staticmethod
    def get_notifications_by_status(
        status: NotificationStatus,
        limit: int = 100,
        offset: int = 0
    ) -> List[Notification]:
        """Obtiene notificaciones por estado"""
        
        try:
            with get_db_session() as db:
                return db.query(Notification).filter(
                    Notification.status == status
                ).order_by(desc(Notification.created_at)).limit(limit).offset(offset).all()
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting notifications by status {status}: {e}")
            return []

    @staticmethod
    def get_notifications_for_retry(max_retries: int = 3) -> List[Notification]:
        """Obtiene notificaciones que necesitan reintento"""
        
        try:
            with get_db_session() as db:
                return db.query(Notification).filter(
                    and_(
                        Notification.status == NotificationStatus.FAILED,
                        Notification.retry_count < max_retries,
                        Notification.created_at > datetime.utcnow() - timedelta(hours=24)
                    )
                ).order_by(Notification.created_at).all()
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting notifications for retry: {e}")
            return []

    @staticmethod
    def add_notification_log(
        message_id: str,
        event_type: str,
        event_status: Optional[str] = None,
        event_message: Optional[str] = None,
        details_json: Optional[Dict[str, Any]] = None,
        component: Optional[str] = None,
        provider: Optional[str] = None,
        processing_time_ms: Optional[int] = None
    ) -> Optional[NotificationLog]:
        """Agrega un log de evento a una notificación"""
        
        try:
            with get_db_session() as db:
                log_entry = NotificationLog(
                    message_id=message_id,
                    event_type=event_type,
                    event_status=event_status,
                    event_message=event_message,
                    details_json=details_json,
                    component=component,
                    provider=provider,
                    processing_time_ms=processing_time_ms
                )
                
                db.add(log_entry)
                db.commit()
                db.refresh(log_entry)
                
                logger.debug(f"Added log for {message_id}: {event_type}")
                return log_entry
                
        except SQLAlchemyError as e:
            logger.error(f"Error adding log for {message_id}: {e}")
            return None

    @staticmethod
    def get_notification_logs(
        message_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[NotificationLog]:
        """Obtiene logs de una notificación"""
        
        try:
            with get_db_session() as db:
                return db.query(NotificationLog).filter(
                    NotificationLog.message_id == message_id
                ).order_by(desc(NotificationLog.timestamp)).limit(limit).offset(offset).all()
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting logs for {message_id}: {e}")
            return []

    @staticmethod
    def search_notifications(
        email: Optional[str] = None,
        template_id: Optional[str] = None,
        provider: Optional[str] = None,
        status: Optional[NotificationStatus] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Notification], int]:
        """Búsqueda avanzada de notificaciones con conteo total"""
        
        try:
            with get_db_session() as db:
                query = db.query(Notification)
                
                # Aplicar filtros
                if email:
                    query = query.filter(Notification.to_email.like(f"%{email}%"))
                if template_id:
                    query = query.filter(Notification.template_id == template_id)
                if provider:
                    query = query.filter(Notification.provider == provider)
                if status:
                    query = query.filter(Notification.status == status)
                if date_from:
                    query = query.filter(Notification.created_at >= date_from)
                if date_to:
                    query = query.filter(Notification.created_at <= date_to)
                
                # Contar total
                total = query.count()
                
                # Obtener resultados paginados
                results = query.order_by(desc(Notification.created_at)).limit(limit).offset(offset).all()
                
                return results, total
                
        except SQLAlchemyError as e:
            logger.error(f"Error searching notifications: {e}")
            return [], 0

    @staticmethod
    def get_notification_with_logs(message_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene notificación completa con sus logs"""
        
        notification = DatabaseService.get_notification(message_id)
        if not notification:
            return None
        
        logs = DatabaseService.get_notification_logs(message_id)
        
        return {
            "notification": notification.to_dict(),
            "logs": [log.to_dict() for log in logs],
            "total_logs": len(logs)
        }

    @staticmethod
    def regenerate_notification_data(message_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene datos para regenerar una notificación"""
        
        notification = DatabaseService.get_notification(message_id)
        if not notification:
            return None
        
        return {
            "template_id": notification.template_id,
            "to_email": notification.to_email,
            "cc_emails": notification.cc_emails,
            "bcc_emails": notification.bcc_emails,
            "params_json": notification.params_json,
            "provider": notification.provider,
            "routing_hint": notification.routing_hint,
            "priority": notification.priority.value if notification.priority else "medium"
        }

    @staticmethod
    def get_provider_stats(
        provider: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Obtiene estadísticas de proveedores"""
        
        try:
            with get_db_session() as db:
                query = db.query(
                    Notification.provider,
                    func.count(Notification.id).label('total'),
                    func.sum(func.case(
                        (Notification.status == NotificationStatus.SENT, 1),
                        else_=0
                    )).label('sent'),
                    func.sum(func.case(
                        (Notification.status == NotificationStatus.FAILED, 1),
                        else_=0
                    )).label('failed'),
                    func.avg(func.case(
                        (Notification.sent_at.isnot(None), 
                         func.timestampdiff('SECOND', Notification.created_at, Notification.sent_at)),
                        else_=None
                    )).label('avg_delivery_seconds')
                ).filter(Notification.provider.isnot(None))
                
                if provider:
                    query = query.filter(Notification.provider == provider)
                if date_from:
                    query = query.filter(Notification.created_at >= date_from)
                if date_to:
                    query = query.filter(Notification.created_at <= date_to)
                
                results = query.group_by(Notification.provider).all()
                
                return [
                    {
                        "provider": r.provider,
                        "total": r.total,
                        "sent": r.sent,
                        "failed": r.failed,
                        "success_rate": round((r.sent / r.total * 100), 2) if r.total > 0 else 0,
                        "avg_delivery_seconds": round(r.avg_delivery_seconds, 2) if r.avg_delivery_seconds else None
                    }
                    for r in results
                ]
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting provider stats: {e}")
            return []

    @staticmethod
    def cleanup_old_notifications(days_to_keep: int = 90) -> int:
        """Elimina notificaciones antiguas"""
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            with get_db_session() as db:
                deleted = db.query(Notification).filter(
                    Notification.created_at < cutoff_date
                ).delete()
                
                db.commit()
                logger.info(f"Cleaned up {deleted} old notifications")
                return deleted
                
        except SQLAlchemyError as e:
            logger.error(f"Error cleaning up notifications: {e}")
            return 0

    # ✅ MÉTODOS ADICIONALES para soporte completo de workers

    @staticmethod
    def update_notification_with_provider_response(
        message_id: str,
        status: NotificationStatus,
        provider_response: Dict[str, Any],
        sent_at: Optional[datetime] = None
    ) -> bool:
        """Actualiza notificación con respuesta del proveedor"""
        
        return DatabaseService.update_notification_status(
            message_id=message_id,
            status=status,
            sent_at=sent_at,
            provider_response=provider_response
        )

    @staticmethod
    def mark_notification_failed(
        message_id: str,
        error_message: str,
        retry_count: Optional[int] = None,
        celery_task_id: Optional[str] = None
    ) -> bool:
        """Marca notificación como fallida"""
        
        return DatabaseService.update_notification_status(
            message_id=message_id,
            status=NotificationStatus.FAILED,
            retry_count=retry_count,
            celery_task_id=celery_task_id,
            error_message=error_message
        )

    @staticmethod
    def mark_notification_sent(
        message_id: str,
        provider_response: Dict[str, Any],
        celery_task_id: Optional[str] = None
    ) -> bool:
        """Marca notificación como enviada exitosamente"""
        
        return DatabaseService.update_notification_status(
            message_id=message_id,
            status=NotificationStatus.SENT,
            sent_at=datetime.utcnow(),
            celery_task_id=celery_task_id,
            provider_response=provider_response
        )

    @staticmethod
    def get_notification_by_task_id(celery_task_id: str) -> Optional[Notification]:
        """Obtiene notificación por celery_task_id"""
        
        try:
            with get_db_session() as db:
                return db.query(Notification).filter(
                    Notification.celery_task_id == celery_task_id
                ).first()
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting notification by task_id {celery_task_id}: {e}")
            return None
        
    # ✅ NUEVOS MÉTODOS PARA PROVIDER_STATS

    @staticmethod
    def update_provider_stats(
        provider: str,
        stat_type: str,  # "sent", "failed", "rejected"
        processing_time_ms: Optional[int] = None,
        stat_date: Optional[date] = None,
        stat_hour: Optional[int] = None
    ) -> bool:
        """
        Actualiza estadísticas de proveedor incrementando contadores
        
        Args:
            provider: Nombre del proveedor
            stat_type: Tipo de estadística ("sent", "failed", "rejected")
            processing_time_ms: Tiempo de procesamiento en milisegundos
            stat_date: Fecha específica (default: hoy)
            stat_hour: Hora específica (default: hora actual)
        """
        from datetime import date
        
        if not stat_date:
            stat_date = date.today()
        if stat_hour is None:
            stat_hour = datetime.now().hour
            
        try:
            with get_db_session() as db:
                # Buscar registro existente
                stats = db.query(ProviderStats).filter(
                    and_(
                        ProviderStats.provider == provider,
                        ProviderStats.stat_date == stat_date,
                        ProviderStats.stat_hour == stat_hour
                    )
                ).first()
                
                # Crear si no existe
                if not stats:
                    stats = ProviderStats(
                        provider=provider,
                        stat_date=stat_date,
                        stat_hour=stat_hour,
                        total_sent=0,
                        total_failed=0,
                        total_rejected=0,
                        avg_processing_time_ms=None,
                        max_processing_time_ms=None
                    )
                    db.add(stats)
                
                # Incrementar contadores según tipo
                if stat_type == "sent":
                    stats.total_sent += 1
                elif stat_type == "failed":
                    stats.total_failed += 1
                elif stat_type == "rejected":
                    stats.total_rejected += 1
                else:
                    logger.warning(f"Unknown stat_type: {stat_type}")
                    return False
                
                # Actualizar métricas de tiempo si se proporciona
                if processing_time_ms is not None:
                    # Calcular nuevo promedio
                    total_messages = stats.total_sent + stats.total_failed + stats.total_rejected
                    if total_messages > 1 and stats.avg_processing_time_ms:
                        # Promedio ponderado
                        stats.avg_processing_time_ms = int(
                            ((stats.avg_processing_time_ms * (total_messages - 1)) + processing_time_ms) / total_messages
                        )
                    else:
                        stats.avg_processing_time_ms = processing_time_ms
                    
                    # Actualizar máximo
                    if not stats.max_processing_time_ms or processing_time_ms > stats.max_processing_time_ms:
                        stats.max_processing_time_ms = processing_time_ms
                
                db.commit()
                logger.debug(f"Updated {provider} stats: {stat_type} +1 (date={stat_date}, hour={stat_hour})")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error updating provider stats for {provider}: {e}")
            return False

    @staticmethod
    def get_provider_stats_detailed(
        provider: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        group_by_hour: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Obtiene estadísticas detalladas de proveedores desde provider_stats
        
        Args:
            provider: Filtrar por proveedor específico
            date_from: Fecha inicio
            date_to: Fecha fin
            group_by_hour: Si agrupar por hora o solo por día
        """
        from datetime import date
        
        try:
            with get_db_session() as db:
                if group_by_hour:
                    # Estadísticas por hora
                    query = db.query(
                        ProviderStats.provider,
                        ProviderStats.stat_date,
                        ProviderStats.stat_hour,
                        func.sum(ProviderStats.total_sent).label('total_sent'),
                        func.sum(ProviderStats.total_failed).label('total_failed'),
                        func.sum(ProviderStats.total_rejected).label('total_rejected'),
                        func.avg(ProviderStats.avg_processing_time_ms).label('avg_processing_time_ms'),
                        func.max(ProviderStats.max_processing_time_ms).label('max_processing_time_ms')
                    ).group_by(
                        ProviderStats.provider,
                        ProviderStats.stat_date,
                        ProviderStats.stat_hour
                    )
                else:
                    # Estadísticas por día
                    query = db.query(
                        ProviderStats.provider,
                        ProviderStats.stat_date,
                        func.sum(ProviderStats.total_sent).label('total_sent'),
                        func.sum(ProviderStats.total_failed).label('total_failed'),
                        func.sum(ProviderStats.total_rejected).label('total_rejected'),
                        func.avg(ProviderStats.avg_processing_time_ms).label('avg_processing_time_ms'),
                        func.max(ProviderStats.max_processing_time_ms).label('max_processing_time_ms')
                    ).group_by(
                        ProviderStats.provider,
                        ProviderStats.stat_date
                    )
                
                # Aplicar filtros
                if provider:
                    query = query.filter(ProviderStats.provider == provider)
                if date_from:
                    query = query.filter(ProviderStats.stat_date >= date_from)
                if date_to:
                    query = query.filter(ProviderStats.stat_date <= date_to)
                
                # Ordenar por fecha
                query = query.order_by(ProviderStats.stat_date.desc())
                
                results = query.all()
                
                stats_list = []
                for r in results:
                    total = r.total_sent + r.total_failed + r.total_rejected
                    success_rate = round((r.total_sent / total * 100), 2) if total > 0 else 0
                    
                    stat_item = {
                        "provider": r.provider,
                        "stat_date": r.stat_date.isoformat(),
                        "total_sent": r.total_sent,
                        "total_failed": r.total_failed,
                        "total_rejected": r.total_rejected,
                        "total_messages": total,
                        "success_rate": success_rate,
                        "avg_processing_time_ms": round(r.avg_processing_time_ms, 2) if r.avg_processing_time_ms else None,
                        "max_processing_time_ms": r.max_processing_time_ms
                    }
                    
                    if group_by_hour:
                        stat_item["stat_hour"] = r.stat_hour
                    
                    stats_list.append(stat_item)
                
                return stats_list
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting detailed provider stats: {e}")
            return []

    @staticmethod
    def get_provider_stats_summary(
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Obtiene resumen de estadísticas de proveedores para los últimos N días
        """
        from datetime import date, timedelta
        
        date_from = date.today() - timedelta(days=days_back)
        
        try:
            with get_db_session() as db:
                query = db.query(
                    ProviderStats.provider,
                    func.sum(ProviderStats.total_sent).label('total_sent'),
                    func.sum(ProviderStats.total_failed).label('total_failed'),
                    func.sum(ProviderStats.total_rejected).label('total_rejected'),
                    func.avg(ProviderStats.avg_processing_time_ms).label('avg_processing_time_ms'),
                    func.max(ProviderStats.max_processing_time_ms).label('max_processing_time_ms')
                ).filter(
                    ProviderStats.stat_date >= date_from
                ).group_by(ProviderStats.provider)
                
                results = query.all()
                
                return [
                    {
                        "provider": r.provider,
                        "days_back": days_back,
                        "total_sent": r.total_sent,
                        "total_failed": r.total_failed,
                        "total_rejected": r.total_rejected,
                        "total_messages": r.total_sent + r.total_failed + r.total_rejected,
                        "success_rate": round((r.total_sent / (r.total_sent + r.total_failed + r.total_rejected) * 100), 2) 
                                      if (r.total_sent + r.total_failed + r.total_rejected) > 0 else 0,
                        "avg_processing_time_ms": round(r.avg_processing_time_ms, 2) if r.avg_processing_time_ms else None,
                        "max_processing_time_ms": r.max_processing_time_ms
                    }
                    for r in results
                ]
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting provider stats summary: {e}")
            return []

    @staticmethod
    def create_provider_stats_entry(
        provider: str,
        stat_date: Optional[date] = None,
        stat_hour: Optional[int] = None
    ) -> bool:
        """
        Crea entrada inicial de estadísticas para un proveedor/fecha/hora si no existe
        """
        from datetime import date
        
        if not stat_date:
            stat_date = date.today()
        if stat_hour is None:
            stat_hour = datetime.now().hour
        
        try:
            with get_db_session() as db:
                # Verificar si ya existe
                existing = db.query(ProviderStats).filter(
                    and_(
                        ProviderStats.provider == provider,
                        ProviderStats.stat_date == stat_date,
                        ProviderStats.stat_hour == stat_hour
                    )
                ).first()
                
                if existing:
                    return True  # Ya existe
                
                # Crear nueva entrada
                stats = ProviderStats(
                    provider=provider,
                    stat_date=stat_date,
                    stat_hour=stat_hour,
                    total_sent=0,
                    total_failed=0,
                    total_rejected=0,
                    avg_processing_time_ms=None,
                    max_processing_time_ms=None
                )
                
                db.add(stats)
                db.commit()
                
                logger.debug(f"Created provider stats entry: {provider} {stat_date} {stat_hour}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error creating provider stats entry: {e}")
            return False