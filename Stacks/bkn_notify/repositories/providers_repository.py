"""
Stacks/bkn_notify/repositories/providers_repository.py
Providers Repository - CRUD operations para providers
Capa de acceso a datos con queries optimizadas
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import and_, or_, desc, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from models.provider_models import Provider, ProviderType, ProviderEnvironment
from utils.database import get_db_session

logger = logging.getLogger(__name__)

# =============================================================================
# ENUM NORMALIZATION HELPERS
# =============================================================================

def _normalize_provider_type(provider_type: str) -> str:
    """Normaliza tipo de provider a UPPERCASE para match con enum BD"""
    if not provider_type:
        return "SMTP"
    return provider_type.upper()


def _normalize_environment(environment: str) -> str:
    """Normaliza ambiente a lowercase para match con enum BD"""
    if not environment:
        return "production"
    return environment.lower()

class ProvidersRepository:
    """
    Repositorio para operaciones CRUD de providers
    """
    
    @staticmethod
    def get_all_providers(environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Obtiene todos los providers
        
        Args:
            environment: Filtrar por ambiente (optional)
            
        Returns:
            Lista de providers como diccionarios
        """
        try:
            with get_db_session() as db:
                query = db.query(Provider)
                
                if environment:
                    query = query.filter(Provider.environment == environment)
                
                providers = query.order_by(Provider.priority.asc()).all()
                return [p.to_dict() for p in providers]
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting all providers: {e}")
            return []
    
    
    @staticmethod
    def get_active_providers(environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Obtiene solo providers activos y saludables
        
        Args:
            environment: Filtrar por ambiente (optional)
            
        Returns:
            Lista de providers activos ordenados por prioridad
        """
        try:
            with get_db_session() as db:
                query = db.query(Provider).filter(
                    and_(
                        Provider.enabled == True,
                        Provider.is_healthy == True
                    )
                )
                
                if environment:
                    query = query.filter(Provider.environment == environment)
                
                providers = query.order_by(Provider.priority.asc()).all()
                return [p.to_dict() for p in providers]
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting active providers: {e}")
            return []
    
    
    @staticmethod
    def get_provider_by_key(provider_key: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene provider por su clave única
        
        Args:
            provider_key: Identificador único del provider
            
        Returns:
            Provider como diccionario o None si no existe
        """
        try:
            with get_db_session() as db:
                provider = db.query(Provider).filter(
                    Provider.provider_key == provider_key
                ).first()
                
                return provider.to_dict() if provider else None
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting provider by key '{provider_key}': {e}")
            return None
    
    
    @staticmethod
    def get_provider_by_id(provider_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene provider por ID
        
        Args:
            provider_id: ID del provider
            
        Returns:
            Provider como diccionario o None si no existe
        """
        try:
            with get_db_session() as db:
                provider = db.query(Provider).filter(
                    Provider.id == provider_id
                ).first()
                
                return provider.to_dict() if provider else None
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting provider by id {provider_id}: {e}")
            return None
    
    
    @staticmethod
    def get_providers_by_type(
        provider_type: str, 
        only_active: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Obtiene providers por tipo
        
        Args:
            provider_type: Tipo de provider (smtp, api, webhook, twilio)
            only_active: Si True, solo retorna activos y saludables
            
        Returns:
            Lista de providers del tipo especificado
        """
        try:
            with get_db_session() as db:
                # NORMALIZAR tipo a UPPERCASE
                normalized_type = _normalize_provider_type(provider_type)
                
                query = db.query(Provider).filter(
                    Provider.provider_type == normalized_type  # <-- USAR NORMALIZADO
                )
                
                if only_active:
                    query = query.filter(
                        and_(
                            Provider.enabled == True,
                            Provider.is_healthy == True
                        )
                    )
                
                providers = query.order_by(Provider.priority.asc()).all()
                return [p.to_dict() for p in providers]
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting providers by type '{provider_type}': {e}")
            return []
    
    @staticmethod
    def create_provider(provider_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crea un nuevo provider
        
        Args:
            provider_data: Datos del provider a crear
            
        Returns:
            Provider creado como diccionario o None si falla
        """
        try:
            with get_db_session() as db:
                # Crear instancia del modelo
                provider = Provider(
                    provider_key=provider_data.get('provider_key'),
                    name=provider_data.get('name'),
                    description=provider_data.get('description'),
                    provider_type=provider_data.get('provider_type'),
                    enabled=provider_data.get('enabled', True),
                    priority=provider_data.get('priority', 100),
                    weight=provider_data.get('weight', 10),
                    max_retries=provider_data.get('max_retries', 3),
                    timeout_seconds=provider_data.get('timeout_seconds', 30),
                    rate_limit_per_minute=provider_data.get('rate_limit_per_minute', 60),
                    config_json=provider_data.get('config_json', {}),
                    credentials_json=provider_data.get('credentials_json'),
                    health_check_enabled=provider_data.get('health_check_enabled', True),
                    health_check_url=provider_data.get('health_check_url'),
                    health_check_interval_minutes=provider_data.get('health_check_interval_minutes', 5),
                    is_healthy=provider_data.get('is_healthy', True),
                    environment=provider_data.get('environment', 'production'),
                    created_by=provider_data.get('created_by')
                )
                
                db.add(provider)
                db.commit()
                db.refresh(provider)
                
                logger.info(f"Provider created: {provider.provider_key}")
                return provider.to_dict()
                
        except IntegrityError as e:
            logger.error(f"Provider key already exists: {e}")
            return None
        except SQLAlchemyError as e:
            logger.error(f"Error creating provider: {e}")
            return None
    
    
    @staticmethod
    def update_provider(
        provider_key: str, 
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza un provider existente
        
        Args:
            provider_key: Identificador único del provider
            update_data: Datos a actualizar
            
        Returns:
            Provider actualizado como diccionario o None si falla
        """
        try:
            with get_db_session() as db:
                provider = db.query(Provider).filter(
                    Provider.provider_key == provider_key
                ).first()
                
                if not provider:
                    logger.warning(f"Provider not found: {provider_key}")
                    return None
                
                # Actualizar campos permitidos
                allowed_fields = [
                    'name', 'description', 'enabled', 'priority', 'weight',
                    'max_retries', 'timeout_seconds', 'rate_limit_per_minute',
                    'config_json', 'credentials_json', 'health_check_enabled',
                    'health_check_url', 'health_check_interval_minutes',
                    'is_healthy', 'last_error_message', 'updated_by'
                ]
                
                for field, value in update_data.items():
                    if field in allowed_fields and hasattr(provider, field):
                        setattr(provider, field, value)
                
                db.commit()
                db.refresh(provider)
                
                logger.info(f"Provider updated: {provider_key}")
                return provider.to_dict()
                
        except SQLAlchemyError as e:
            logger.error(f"Error updating provider '{provider_key}': {e}")
            return None
    
    
    @staticmethod
    def toggle_provider_status(
        provider_key: str, 
        enabled: bool,
        updated_by: Optional[str] = None
    ) -> bool:
        """
        Habilita o deshabilita un provider
        
        Args:
            provider_key: Identificador único del provider
            enabled: True para habilitar, False para deshabilitar
            updated_by: Usuario que realiza el cambio
            
        Returns:
            True si se actualizó correctamente, False si falla
        """
        try:
            with get_db_session() as db:
                provider = db.query(Provider).filter(
                    Provider.provider_key == provider_key
                ).first()
                
                if not provider:
                    logger.warning(f"Provider not found: {provider_key}")
                    return False
                
                provider.enabled = enabled
                if updated_by:
                    provider.updated_by = updated_by
                
                db.commit()
                
                status = "enabled" if enabled else "disabled"
                logger.info(f"Provider {status}: {provider_key}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error toggling provider status '{provider_key}': {e}")
            return False
    
    
    @staticmethod
    def update_health_status(
        provider_key: str,
        is_healthy: bool,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Actualiza el estado de salud de un provider
        
        Args:
            provider_key: Identificador único del provider
            is_healthy: True si está saludable, False si no
            error_message: Mensaje de error si is_healthy=False
            
        Returns:
            True si se actualizó correctamente, False si falla
        """
        try:
            with get_db_session() as db:
                provider = db.query(Provider).filter(
                    Provider.provider_key == provider_key
                ).first()
                
                if not provider:
                    logger.warning(f"Provider not found: {provider_key}")
                    return False
                
                provider.is_healthy = is_healthy
                provider.last_health_check = datetime.now()
                
                if not is_healthy and error_message:
                    provider.last_error_message = error_message
                elif is_healthy:
                    provider.last_error_message = None
                
                db.commit()
                
                status = "healthy" if is_healthy else "unhealthy"
                logger.info(f"Provider health updated to {status}: {provider_key}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error updating health status '{provider_key}': {e}")
            return False
    
    
    @staticmethod
    def delete_provider(provider_key: str) -> bool:
        """
        Elimina un provider (soft delete - deshabilita)
        
        Args:
            provider_key: Identificador único del provider
            
        Returns:
            True si se eliminó correctamente, False si falla
        """
        try:
            with get_db_session() as db:
                provider = db.query(Provider).filter(
                    Provider.provider_key == provider_key
                ).first()
                
                if not provider:
                    logger.warning(f"Provider not found: {provider_key}")
                    return False
                
                # Soft delete: solo deshabilitar
                provider.enabled = False
                db.commit()
                
                logger.info(f"Provider soft-deleted (disabled): {provider_key}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error deleting provider '{provider_key}': {e}")
            return False
    
    
    @staticmethod
    def get_providers_stats() -> Dict[str, Any]:
        """
        Obtiene estadísticas generales de providers
        
        Returns:
            Diccionario con estadísticas agregadas
        """
        try:
            with get_db_session() as db:
                total = db.query(func.count(Provider.id)).scalar()
                enabled = db.query(func.count(Provider.id)).filter(
                    Provider.enabled == True
                ).scalar()
                healthy = db.query(func.count(Provider.id)).filter(
                    and_(
                        Provider.enabled == True,
                        Provider.is_healthy == True
                    )
                ).scalar()
                
                by_type = db.query(
                    Provider.provider_type,
                    func.count(Provider.id)
                ).group_by(Provider.provider_type).all()
                
                return {
                    "total_providers": total,
                    "enabled_providers": enabled,
                    "healthy_providers": healthy,
                    "unhealthy_providers": enabled - healthy if enabled else 0,
                    "disabled_providers": total - enabled if total else 0,
                    "by_type": {str(pt): count for pt, count in by_type}
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting providers stats: {e}")
            return {
                "total_providers": 0,
                "enabled_providers": 0,
                "healthy_providers": 0,
                "unhealthy_providers": 0,
                "disabled_providers": 0,
                "by_type": {}
            }