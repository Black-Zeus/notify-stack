"""
Stacks/bkn_notify/repositories/provider_groups_repository.py
Provider Groups Repository - CRUD operations para grupos y membresías
Gestión de agrupación de providers y reglas de routing
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import and_, or_, desc, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from models.provider_models import (
    ProviderGroup, ProviderGroupMember, ProviderGroupRouting,
    Provider, RoutingStrategy, ProviderEnvironment
)
from utils.database import get_db_session

logger = logging.getLogger(__name__)

# =============================================================================
# ENUM NORMALIZATION HELPERS
# =============================================================================

def _normalize_routing_strategy(strategy: str) -> str:
    """Normaliza routing strategy a UPPERCASE para match con enum BD"""
    if not strategy:
        return "PRIORITY"
    return strategy.upper()


def _normalize_environment(environment: str) -> str:
    """Normaliza ambiente a lowercase para match con enum BD"""
    if not environment:
        return "production"
    return environment.lower()

class ProviderGroupsRepository:
    """
    Repositorio para operaciones CRUD de grupos y membresías
    """
    
    # ==========================================================================
    # GRUPOS - CRUD BÁSICO
    # ==========================================================================
    
    @staticmethod
    def get_all_groups(environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Obtiene todos los grupos de providers
        
        Args:
            environment: Filtrar por ambiente (optional)
            
        Returns:
            Lista de grupos como diccionarios
        """
        try:
            with get_db_session() as db:
                query = db.query(ProviderGroup)
                
                if environment:
                    query = query.filter(ProviderGroup.environment == environment)
                
                groups = query.order_by(ProviderGroup.name.asc()).all()
                return [g.to_dict() for g in groups]
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting all groups: {e}")
            return []
    
    
    @staticmethod
    def get_active_groups(environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Obtiene solo grupos activos
        
        Args:
            environment: Filtrar por ambiente (optional)
            
        Returns:
            Lista de grupos activos
        """
        try:
            with get_db_session() as db:
                query = db.query(ProviderGroup).filter(
                    ProviderGroup.enabled == True
                )
                
                if environment:
                    query = query.filter(ProviderGroup.environment == environment)
                
                groups = query.order_by(ProviderGroup.name.asc()).all()
                return [g.to_dict() for g in groups]
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting active groups: {e}")
            return []
    
    
    @staticmethod
    def get_group_by_key(group_key: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene grupo por su clave única
        
        Args:
            group_key: Identificador único del grupo
            
        Returns:
            Grupo como diccionario o None si no existe
        """
        try:
            with get_db_session() as db:
                group = db.query(ProviderGroup).filter(
                    ProviderGroup.group_key == group_key
                ).first()
                
                return group.to_dict() if group else None
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting group by key '{group_key}': {e}")
            return None
    
    
    @staticmethod
    def create_group(group_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crea un nuevo grupo de providers
        
        Args:
            group_data: Datos del grupo a crear
            
        Returns:
            Grupo creado como diccionario o None si falla
        """
        try:
            with get_db_session() as db:
                # NORMALIZAR strategy
                strategy = group_data.get('routing_strategy', 'priority')
                normalized_strategy = _normalize_routing_strategy(strategy)
                
                group = ProviderGroup(
                    group_key=group_data.get('group_key'),
                    name=group_data.get('name'),
                    description=group_data.get('description'),
                    routing_strategy=normalized_strategy,  # <-- USAR NORMALIZADO
                    failover_enabled=group_data.get('failover_enabled', True),
                    failover_timeout_seconds=group_data.get('failover_timeout_seconds', 30),
                    max_group_retries=group_data.get('max_group_retries', 2),
                    retry_delay_seconds=group_data.get('retry_delay_seconds', 5),
                    enabled=group_data.get('enabled', True),
                    environment=group_data.get('environment', 'production'),
                    created_by=group_data.get('created_by')
                )
                
                db.add(group)
                db.commit()
                db.refresh(group)
                
                logger.info(f"Group created: {group.group_key}")
                return group.to_dict()
                
        except IntegrityError as e:
            logger.error(f"Group key already exists: {e}")
            return None
        except SQLAlchemyError as e:
            logger.error(f"Error creating group: {e}")
            return None
    
    @staticmethod
    def update_group(
        group_key: str, 
        update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza un grupo existente
        
        Args:
            group_key: Identificador único del grupo
            update_data: Datos a actualizar
            
        Returns:
            Grupo actualizado como diccionario o None si falla
        """
        try:
            with get_db_session() as db:
                group = db.query(ProviderGroup).filter(
                    ProviderGroup.group_key == group_key
                ).first()
                
                if not group:
                    logger.warning(f"Group not found: {group_key}")
                    return None
                
                # Actualizar campos permitidos
                allowed_fields = [
                    'name', 'description', 'routing_strategy', 
                    'failover_enabled', 'failover_timeout_seconds',
                    'max_group_retries', 'retry_delay_seconds',
                    'enabled', 'updated_by'
                ]
                
                for field, value in update_data.items():
                    if field in allowed_fields and hasattr(group, field):
                        setattr(group, field, value)
                
                db.commit()
                db.refresh(group)
                
                logger.info(f"Group updated: {group_key}")
                return group.to_dict()
                
        except SQLAlchemyError as e:
            logger.error(f"Error updating group '{group_key}': {e}")
            return None
    
    
    @staticmethod
    def delete_group(group_key: str) -> bool:
        """
        Elimina un grupo (soft delete - deshabilita)
        
        Args:
            group_key: Identificador único del grupo
            
        Returns:
            True si se eliminó correctamente, False si falla
        """
        try:
            with get_db_session() as db:
                group = db.query(ProviderGroup).filter(
                    ProviderGroup.group_key == group_key
                ).first()
                
                if not group:
                    logger.warning(f"Group not found: {group_key}")
                    return False
                
                # Soft delete: solo deshabilitar
                group.enabled = False
                db.commit()
                
                logger.info(f"Group soft-deleted (disabled): {group_key}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error deleting group '{group_key}': {e}")
            return False
    
    
    # ==========================================================================
    # MEMBRESÍAS - GESTIÓN PROVIDERS EN GRUPOS
    # ==========================================================================
    
    @staticmethod
    def get_group_members(
        group_key: str, 
        only_enabled: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Obtiene todos los providers de un grupo con sus configuraciones
        
        Args:
            group_key: Identificador único del grupo
            only_enabled: Si True, solo retorna miembros habilitados
            
        Returns:
            Lista de providers del grupo con metadata de membresía
        """
        try:
            with get_db_session() as db:
                # Obtener el grupo
                group = db.query(ProviderGroup).filter(
                    ProviderGroup.group_key == group_key
                ).first()
                
                if not group:
                    logger.warning(f"Group not found: {group_key}")
                    return []
                
                # Query con join para traer providers completos
                query = db.query(
                    ProviderGroupMember, Provider
                ).join(
                    Provider, ProviderGroupMember.provider_id == Provider.id
                ).filter(
                    ProviderGroupMember.group_id == group.id
                )
                
                if only_enabled:
                    query = query.filter(
                        and_(
                            ProviderGroupMember.enabled == True,
                            Provider.enabled == True,
                            Provider.is_healthy == True
                        )
                    )
                
                # Ordenar por prioridad
                query = query.order_by(ProviderGroupMember.priority.asc())
                
                results = []
                for member, provider in query.all():
                    member_data = member.to_dict()
                    member_data['provider'] = provider.to_dict()
                    results.append(member_data)
                
                return results
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting group members '{group_key}': {e}")
            return []
    
    
    @staticmethod
    def add_provider_to_group(
        group_key: str,
        provider_key: str,
        priority: int = 100,
        weight: int = 10,
        enabled: bool = True,
        added_by: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Agrega un provider a un grupo
        
        Args:
            group_key: Identificador del grupo
            provider_key: Identificador del provider
            priority: Prioridad dentro del grupo (menor = mayor prioridad)
            weight: Peso para load balancing
            enabled: Si está habilitado en el grupo
            added_by: Usuario que agrega
            
        Returns:
            Membresía creada como diccionario o None si falla
        """
        try:
            with get_db_session() as db:
                # Buscar grupo y provider
                group = db.query(ProviderGroup).filter(
                    ProviderGroup.group_key == group_key
                ).first()
                
                provider = db.query(Provider).filter(
                    Provider.provider_key == provider_key
                ).first()
                
                if not group:
                    logger.warning(f"Group not found: {group_key}")
                    return None
                
                if not provider:
                    logger.warning(f"Provider not found: {provider_key}")
                    return None
                
                # Crear membresía
                member = ProviderGroupMember(
                    group_id=group.id,
                    provider_id=provider.id,
                    priority=priority,
                    weight=weight,
                    enabled=enabled,
                    added_by=added_by
                )
                
                db.add(member)
                db.commit()
                db.refresh(member)
                
                logger.info(f"Provider '{provider_key}' added to group '{group_key}'")
                return member.to_dict()
                
        except IntegrityError as e:
            logger.error(f"Provider already in group: {e}")
            return None
        except SQLAlchemyError as e:
            logger.error(f"Error adding provider to group: {e}")
            return None
    
    
    @staticmethod
    def remove_provider_from_group(
        group_key: str,
        provider_key: str
    ) -> bool:
        """
        Remueve un provider de un grupo
        
        Args:
            group_key: Identificador del grupo
            provider_key: Identificador del provider
            
        Returns:
            True si se removió correctamente, False si falla
        """
        try:
            with get_db_session() as db:
                # Buscar grupo y provider
                group = db.query(ProviderGroup).filter(
                    ProviderGroup.group_key == group_key
                ).first()
                
                provider = db.query(Provider).filter(
                    Provider.provider_key == provider_key
                ).first()
                
                if not group or not provider:
                    logger.warning(f"Group or provider not found")
                    return False
                
                # Eliminar membresía
                member = db.query(ProviderGroupMember).filter(
                    and_(
                        ProviderGroupMember.group_id == group.id,
                        ProviderGroupMember.provider_id == provider.id
                    )
                ).first()
                
                if not member:
                    logger.warning(f"Provider not in group")
                    return False
                
                db.delete(member)
                db.commit()
                
                logger.info(f"Provider '{provider_key}' removed from group '{group_key}'")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error removing provider from group: {e}")
            return False
    
    
    @staticmethod
    def update_member_priority(
        group_key: str,
        provider_key: str,
        priority: int
    ) -> bool:
        """
        Actualiza la prioridad de un provider en un grupo
        
        Args:
            group_key: Identificador del grupo
            provider_key: Identificador del provider
            priority: Nueva prioridad
            
        Returns:
            True si se actualizó correctamente, False si falla
        """
        try:
            with get_db_session() as db:
                group = db.query(ProviderGroup).filter(
                    ProviderGroup.group_key == group_key
                ).first()
                
                provider = db.query(Provider).filter(
                    Provider.provider_key == provider_key
                ).first()
                
                if not group or not provider:
                    return False
                
                member = db.query(ProviderGroupMember).filter(
                    and_(
                        ProviderGroupMember.group_id == group.id,
                        ProviderGroupMember.provider_id == provider.id
                    )
                ).first()
                
                if not member:
                    return False
                
                member.priority = priority
                db.commit()
                
                logger.info(f"Updated priority for '{provider_key}' in group '{group_key}' to {priority}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Error updating member priority: {e}")
            return False
    
    
    # ==========================================================================
    # QUERIES ESPECIALIZADAS PARA ROUTING
    # ==========================================================================
    
    @staticmethod
    def get_group_with_active_providers(group_key: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene grupo completo con todos sus providers activos ordenados
        Optimizado para decisiones de routing
        
        Args:
            group_key: Identificador del grupo
            
        Returns:
            Diccionario con grupo y lista de providers activos ordenados
        """
        try:
            with get_db_session() as db:
                group = db.query(ProviderGroup).filter(
                    and_(
                        ProviderGroup.group_key == group_key,
                        ProviderGroup.enabled == True
                    )
                ).first()
                
                if not group:
                    return None
                
                # Obtener providers activos del grupo
                members = ProviderGroupsRepository.get_group_members(
                    group_key, 
                    only_enabled=True
                )
                
                return {
                    "group": group.to_dict(),
                    "providers": members,
                    "total_providers": len(members),
                    "routing_strategy": group.routing_strategy.value
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting group with providers '{group_key}': {e}")
            return None
    
    
    @staticmethod
    def get_groups_stats() -> Dict[str, Any]:
        """
        Obtiene estadísticas generales de grupos
        
        Returns:
            Diccionario con estadísticas agregadas
        """
        try:
            with get_db_session() as db:
                total = db.query(func.count(ProviderGroup.id)).scalar()
                enabled = db.query(func.count(ProviderGroup.id)).filter(
                    ProviderGroup.enabled == True
                ).scalar()
                
                by_strategy = db.query(
                    ProviderGroup.routing_strategy,
                    func.count(ProviderGroup.id)
                ).group_by(ProviderGroup.routing_strategy).all()
                
                return {
                    "total_groups": total,
                    "enabled_groups": enabled,
                    "disabled_groups": total - enabled if total else 0,
                    "by_strategy": {str(strategy): count for strategy, count in by_strategy}
                }
                
        except SQLAlchemyError as e:
            logger.error(f"Error getting groups stats: {e}")
            return {
                "total_groups": 0,
                "enabled_groups": 0,
                "disabled_groups": 0,
                "by_strategy": {}
            }