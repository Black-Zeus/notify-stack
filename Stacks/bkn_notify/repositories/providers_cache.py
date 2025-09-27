"""
Stacks/bkn_notify/repositories/providers_cache.py
Providers Cache - Cache Redis para providers y grupos
Optimización de queries con TTL y invalidación automática
"""

import json
import logging
from typing import List, Optional, Dict, Any, Callable
from functools import wraps

import redis
from redis.exceptions import RedisError, ConnectionError

from repositories.providers_repository import ProvidersRepository
from repositories.provider_groups_repository import ProviderGroupsRepository

logger = logging.getLogger(__name__)


class ProvidersCache:
    """
    Cache Redis para providers y grupos con fallback automático
    """
    
    # TTL por defecto: 5 minutos
    DEFAULT_TTL = 300
    
    # Prefijos de claves
    PREFIX_PROVIDER = "provider:"
    PREFIX_PROVIDERS_ALL = "providers:all"
    PREFIX_PROVIDERS_ACTIVE = "providers:active"
    PREFIX_PROVIDERS_TYPE = "providers:type:"
    PREFIX_GROUP = "group:"
    PREFIX_GROUPS_ALL = "groups:all"
    PREFIX_GROUPS_ACTIVE = "groups:active"
    PREFIX_GROUP_MEMBERS = "group:members:"
    PREFIX_GROUP_WITH_PROVIDERS = "group:full:"
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, ttl: int = DEFAULT_TTL):
        """
        Inicializa cache con cliente Redis
        
        Args:
            redis_client: Cliente Redis configurado (opcional)
            ttl: Time-to-live por defecto en segundos
        """
        self.redis_client = redis_client
        self.ttl = ttl
        self.enabled = redis_client is not None
        
        if not self.enabled:
            logger.warning("Redis client not provided - cache disabled")
    
    
    def _get_cache_key(self, prefix: str, *args) -> str:
        """Construye clave de cache consistente"""
        parts = [prefix] + [str(arg) for arg in args if arg]
        return ":".join(parts)
    
    
    def _serialize(self, data: Any) -> str:
        """Serializa datos a JSON"""
        return json.dumps(data, default=str)
    
    
    def _deserialize(self, data: str) -> Any:
        """Deserializa JSON a datos"""
        return json.loads(data) if data else None
    
    
    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene valor del cache
        
        Args:
            key: Clave de cache
            
        Returns:
            Valor deserializado o None si no existe/falla
        """
        if not self.enabled:
            return None
        
        try:
            data = self.redis_client.get(key)
            if data:
                logger.debug(f"Cache HIT: {key}")
                return self._deserialize(data)
            else:
                logger.debug(f"Cache MISS: {key}")
                return None
                
        except RedisError as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            return None
    
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Guarda valor en cache con TTL
        
        Args:
            key: Clave de cache
            value: Valor a guardar
            ttl: Time-to-live en segundos (usa default si None)
            
        Returns:
            True si se guardó correctamente, False si falla
        """
        if not self.enabled:
            return False
        
        try:
            ttl = ttl or self.ttl
            serialized = self._serialize(value)
            self.redis_client.setex(key, ttl, serialized)
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
            
        except RedisError as e:
            logger.error(f"Redis SET error for key '{key}': {e}")
            return False
    
    
    def delete(self, key: str) -> bool:
        """
        Elimina clave del cache
        
        Args:
            key: Clave a eliminar
            
        Returns:
            True si se eliminó, False si falla
        """
        if not self.enabled:
            return False
        
        try:
            self.redis_client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
            
        except RedisError as e:
            logger.error(f"Redis DELETE error for key '{key}': {e}")
            return False
    
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Elimina todas las claves que coincidan con un patrón
        
        Args:
            pattern: Patrón de búsqueda (ej: "providers:*")
            
        Returns:
            Número de claves eliminadas
        """
        if not self.enabled:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"Cache PATTERN DELETE: {pattern} ({deleted} keys)")
                return deleted
            return 0
            
        except RedisError as e:
            logger.error(f"Redis PATTERN DELETE error for '{pattern}': {e}")
            return 0
    
    
    def invalidate_all_providers(self) -> bool:
        """Invalida todo el cache de providers"""
        try:
            self.delete_pattern(f"{self.PREFIX_PROVIDER}*")
            self.delete_pattern(f"{self.PREFIX_PROVIDERS_ALL}*")
            self.delete_pattern(f"{self.PREFIX_PROVIDERS_ACTIVE}*")
            self.delete_pattern(f"{self.PREFIX_PROVIDERS_TYPE}*")
            logger.info("All providers cache invalidated")
            return True
        except Exception as e:
            logger.error(f"Error invalidating providers cache: {e}")
            return False
    
    
    def invalidate_all_groups(self) -> bool:
        """Invalida todo el cache de grupos"""
        try:
            self.delete_pattern(f"{self.PREFIX_GROUP}*")
            self.delete_pattern(f"{self.PREFIX_GROUPS_ALL}*")
            self.delete_pattern(f"{self.PREFIX_GROUPS_ACTIVE}*")
            self.delete_pattern(f"{self.PREFIX_GROUP_MEMBERS}*")
            self.delete_pattern(f"{self.PREFIX_GROUP_WITH_PROVIDERS}*")
            logger.info("All groups cache invalidated")
            return True
        except Exception as e:
            logger.error(f"Error invalidating groups cache: {e}")
            return False
    
    
    # ==========================================================================
    # MÉTODOS ESPECÍFICOS PARA PROVIDERS
    # ==========================================================================
    
    def get_all_providers(self, environment: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Obtiene todos los providers desde cache"""
        key = self._get_cache_key(self.PREFIX_PROVIDERS_ALL, environment or "all")
        return self.get(key)
    
    
    def set_all_providers(
        self, 
        providers: List[Dict[str, Any]], 
        environment: Optional[str] = None
    ) -> bool:
        """Guarda lista de providers en cache"""
        key = self._get_cache_key(self.PREFIX_PROVIDERS_ALL, environment or "all")
        return self.set(key, providers)
    
    
    def get_active_providers(self, environment: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Obtiene providers activos desde cache"""
        key = self._get_cache_key(self.PREFIX_PROVIDERS_ACTIVE, environment or "all")
        return self.get(key)
    
    
    def set_active_providers(
        self, 
        providers: List[Dict[str, Any]], 
        environment: Optional[str] = None
    ) -> bool:
        """Guarda providers activos en cache"""
        key = self._get_cache_key(self.PREFIX_PROVIDERS_ACTIVE, environment or "all")
        return self.set(key, providers)
    
    
    def get_provider_by_key(self, provider_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene provider individual desde cache"""
        key = self._get_cache_key(self.PREFIX_PROVIDER, provider_key)
        return self.get(key)
    
    
    def set_provider(self, provider: Dict[str, Any]) -> bool:
        """Guarda provider individual en cache"""
        key = self._get_cache_key(self.PREFIX_PROVIDER, provider.get('provider_key'))
        return self.set(key, provider)
    
    
    def invalidate_provider(self, provider_key: str) -> bool:
        """Invalida cache de un provider específico"""
        key = self._get_cache_key(self.PREFIX_PROVIDER, provider_key)
        # También invalida listas agregadas
        self.delete_pattern(f"{self.PREFIX_PROVIDERS_ALL}*")
        self.delete_pattern(f"{self.PREFIX_PROVIDERS_ACTIVE}*")
        return self.delete(key)
    
    
    def get_providers_by_type(
        self, 
        provider_type: str, 
        only_active: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """Obtiene providers por tipo desde cache"""
        suffix = "active" if only_active else "all"
        key = self._get_cache_key(self.PREFIX_PROVIDERS_TYPE, provider_type, suffix)
        return self.get(key)
    
    
    def set_providers_by_type(
        self, 
        provider_type: str,
        providers: List[Dict[str, Any]],
        only_active: bool = False
    ) -> bool:
        """Guarda providers por tipo en cache"""
        suffix = "active" if only_active else "all"
        key = self._get_cache_key(self.PREFIX_PROVIDERS_TYPE, provider_type, suffix)
        return self.set(key, providers)
    
    
    # ==========================================================================
    # MÉTODOS ESPECÍFICOS PARA GRUPOS
    # ==========================================================================
    
    def get_group_by_key(self, group_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene grupo desde cache"""
        key = self._get_cache_key(self.PREFIX_GROUP, group_key)
        return self.get(key)
    
    
    def set_group(self, group: Dict[str, Any]) -> bool:
        """Guarda grupo en cache"""
        key = self._get_cache_key(self.PREFIX_GROUP, group.get('group_key'))
        return self.set(key, group)
    
    
    def invalidate_group(self, group_key: str) -> bool:
        """Invalida cache de un grupo específico"""
        key = self._get_cache_key(self.PREFIX_GROUP, group_key)
        # También invalida sus miembros y listas agregadas
        self.delete_pattern(f"{self.PREFIX_GROUP_MEMBERS}{group_key}*")
        self.delete_pattern(f"{self.PREFIX_GROUP_WITH_PROVIDERS}{group_key}*")
        self.delete_pattern(f"{self.PREFIX_GROUPS_ALL}*")
        self.delete_pattern(f"{self.PREFIX_GROUPS_ACTIVE}*")
        return self.delete(key)
    
    
    def get_group_members(
        self, 
        group_key: str, 
        only_enabled: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """Obtiene miembros de grupo desde cache"""
        suffix = "enabled" if only_enabled else "all"
        key = self._get_cache_key(self.PREFIX_GROUP_MEMBERS, group_key, suffix)
        return self.get(key)
    
    
    def set_group_members(
        self, 
        group_key: str,
        members: List[Dict[str, Any]],
        only_enabled: bool = False
    ) -> bool:
        """Guarda miembros de grupo en cache"""
        suffix = "enabled" if only_enabled else "all"
        key = self._get_cache_key(self.PREFIX_GROUP_MEMBERS, group_key, suffix)
        return self.set(key, members)
    
    
    def get_group_with_providers(self, group_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene grupo completo con providers desde cache"""
        key = self._get_cache_key(self.PREFIX_GROUP_WITH_PROVIDERS, group_key)
        return self.get(key)
    
    
    def set_group_with_providers(
        self, 
        group_key: str,
        group_data: Dict[str, Any]
    ) -> bool:
        """Guarda grupo completo con providers en cache"""
        key = self._get_cache_key(self.PREFIX_GROUP_WITH_PROVIDERS, group_key)
        return self.set(key, group_data)
    
    
    # ==========================================================================
    # DECORADOR PARA AUTO-CACHE
    # ==========================================================================
    
    @staticmethod
    def cached(cache_key_builder: Callable, ttl: Optional[int] = None):
        """
        Decorador para cachear automáticamente resultados de funciones
        
        Args:
            cache_key_builder: Función que construye la clave de cache
            ttl: Time-to-live en segundos
            
        Usage:
            @ProvidersCache.cached(lambda args: f"key:{args[0]}")
            def my_function(param):
                return expensive_operation(param)
        """
        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                # Intentar obtener del cache
                cache_key = cache_key_builder(args, kwargs)
                
                if hasattr(self, 'cache') and self.cache.enabled:
                    cached_result = self.cache.get(cache_key)
                    if cached_result is not None:
                        return cached_result
                
                # Ejecutar función original
                result = func(self, *args, **kwargs)
                
                # Guardar en cache si está habilitado
                if hasattr(self, 'cache') and self.cache.enabled and result is not None:
                    self.cache.set(cache_key, result, ttl)
                
                return result
            
            return wrapper
        return decorator
    
    
    # ==========================================================================
    # UTILIDADES
    # ==========================================================================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache"""
        if not self.enabled:
            return {"enabled": False, "message": "Cache disabled"}
        
        try:
            info = self.redis_client.info("stats")
            keyspace = self.redis_client.info("keyspace")
            
            # Contar claves por prefijo
            provider_keys = len(self.redis_client.keys(f"{self.PREFIX_PROVIDER}*"))
            group_keys = len(self.redis_client.keys(f"{self.PREFIX_GROUP}*"))
            
            return {
                "enabled": True,
                "connected": True,
                "total_keys": sum(db.get('keys', 0) for db in keyspace.values()),
                "provider_keys": provider_keys,
                "group_keys": group_keys,
                "hits": info.get('keyspace_hits', 0),
                "misses": info.get('keyspace_misses', 0),
                "hit_rate": round(
                    info.get('keyspace_hits', 0) / 
                    (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1)) * 100, 
                    2
                )
            }
            
        except RedisError as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                "enabled": True,
                "connected": False,
                "error": str(e)
            }
    
    
    def ping(self) -> bool:
        """Verifica conexión con Redis"""
        if not self.enabled:
            return False
        
        try:
            return self.redis_client.ping()
        except RedisError:
            return False