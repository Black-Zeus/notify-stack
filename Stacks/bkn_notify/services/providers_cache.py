"""
Stacks/bkn_notify/services/providers_cache.py
Providers Cache Service - Cache Redis para proveedores
Optimización de performance para acceso frecuente a configuración de providers
"""

import logging
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

import redis
from redis.exceptions import RedisError

from models.provider_models import Provider, ProviderGroup, ProviderGroupMember
import constants

logger = logging.getLogger(__name__)


class ProvidersCache:
    """Service para cache Redis de configuración de providers"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """Inicializa el servicio de cache"""
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.from_url(constants.REDIS_URL, decode_responses=True)
        
        # Cache keys prefixes
        self.PROVIDER_KEY_PREFIX = "provider:"
        self.PROVIDERS_LIST_KEY = "providers:all"
        self.ACTIVE_PROVIDERS_KEY = "providers:active"
        self.GROUP_KEY_PREFIX = "provider_group:"
        self.GROUP_MEMBERS_KEY_PREFIX = "group_members:"
        self.PROVIDER_CONFIG_PREFIX = "provider_config:"
        self.PROVIDER_HEALTH_PREFIX = "provider_health:"
        
        # TTL configurations
        self.DEFAULT_TTL = getattr(constants, 'REDIS_TTL_PROVIDERS', 3600)  # 1 hora
        self.HEALTH_TTL = getattr(constants, 'REDIS_TTL_HEALTH', 300)      # 5 minutos
        self.CONFIG_TTL = getattr(constants, 'REDIS_TTL_CONFIG', 1800)     # 30 minutos

    def _generate_cache_key(self, prefix: str, identifier: str) -> str:
        """Genera clave de cache consistente"""
        return f"{prefix}{identifier}"

    def _generate_hash(self, data: Any) -> str:
        """Genera hash MD5 para invalidación de cache"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)
        return hashlib.md5(data_str.encode()).hexdigest()

    def _serialize_provider(self, provider: Provider) -> Dict[str, Any]:
        """Serializa provider para almacenamiento en cache"""
        try:
            provider_dict = provider.to_dict()
            
            # Agregar metadatos de cache
            provider_dict['_cached_at'] = datetime.utcnow().isoformat()
            provider_dict['_cache_version'] = 1
            
            return provider_dict
            
        except Exception as e:
            logger.error(f"Error serializing provider {provider.provider_key}: {e}")
            return {}

    def _deserialize_provider(self, provider_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Deserializa provider desde cache"""
        try:
            # Verificar versión de cache
            if provider_data.get('_cache_version', 0) < 1:
                logger.warning("Outdated cache version found, invalidating")
                return None
            
            # Remover metadatos de cache
            provider_data.pop('_cached_at', None)
            provider_data.pop('_cache_version', None)
            
            return provider_data
            
        except Exception as e:
            logger.error(f"Error deserializing provider from cache: {e}")
            return None

    # =============================================================================
    # PROVIDER CACHING
    # =============================================================================

    def get_provider(self, provider_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene provider desde cache"""
        try:
            cache_key = self._generate_cache_key(self.PROVIDER_KEY_PREFIX, provider_key)
            cached_data = self.redis.get(cache_key)
            
            if cached_data:
                provider_data = json.loads(cached_data)
                return self._deserialize_provider(provider_data)
            
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting provider {provider_key} from cache: {e}")
            return None

    def set_provider(self, provider: Provider, ttl: Optional[int] = None) -> bool:
        """Almacena provider en cache"""
        try:
            cache_key = self._generate_cache_key(self.PROVIDER_KEY_PREFIX, provider.provider_key)
            provider_data = self._serialize_provider(provider)
            
            if not provider_data:
                return False
            
            ttl = ttl or self.DEFAULT_TTL
            self.redis.setex(cache_key, ttl, json.dumps(provider_data))
            
            logger.debug(f"Cached provider {provider.provider_key} with TTL {ttl}s")
            return True
            
        except RedisError as e:
            logger.error(f"Error caching provider {provider.provider_key}: {e}")
            return False

    def get_active_providers(self) -> Optional[List[Dict[str, Any]]]:
        """Obtiene lista de providers activos desde cache"""
        try:
            cached_data = self.redis.get(self.ACTIVE_PROVIDERS_KEY)
            
            if cached_data:
                providers_data = json.loads(cached_data)
                return [
                    self._deserialize_provider(p) 
                    for p in providers_data 
                    if self._deserialize_provider(p) is not None
                ]
            
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting active providers from cache: {e}")
            return None

    def set_active_providers(self, providers: List[Provider], ttl: Optional[int] = None) -> bool:
        """Almacena lista de providers activos en cache"""
        try:
            providers_data = []
            for provider in providers:
                serialized = self._serialize_provider(provider)
                if serialized:
                    providers_data.append(serialized)
            
            ttl = ttl or self.DEFAULT_TTL
            self.redis.setex(self.ACTIVE_PROVIDERS_KEY, ttl, json.dumps(providers_data))
            
            # También cachear providers individuales
            for provider in providers:
                self.set_provider(provider, ttl)
            
            logger.debug(f"Cached {len(providers_data)} active providers with TTL {ttl}s")
            return True
            
        except RedisError as e:
            logger.error(f"Error caching active providers: {e}")
            return False

    def get_providers_by_type(self, provider_type: str) -> Optional[List[Dict[str, Any]]]:
        """Obtiene providers por tipo desde cache"""
        try:
            cache_key = f"providers:type:{provider_type}"
            cached_data = self.redis.get(cache_key)
            
            if cached_data:
                providers_data = json.loads(cached_data)
                return [
                    self._deserialize_provider(p) 
                    for p in providers_data 
                    if self._deserialize_provider(p) is not None
                ]
            
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting providers by type {provider_type} from cache: {e}")
            return None

    def set_providers_by_type(self, provider_type: str, providers: List[Provider], ttl: Optional[int] = None) -> bool:
        """Almacena providers por tipo en cache"""
        try:
            cache_key = f"providers:type:{provider_type}"
            providers_data = []
            
            for provider in providers:
                serialized = self._serialize_provider(provider)
                if serialized:
                    providers_data.append(serialized)
            
            ttl = ttl or self.DEFAULT_TTL
            self.redis.setex(cache_key, ttl, json.dumps(providers_data))
            
            logger.debug(f"Cached {len(providers_data)} providers of type {provider_type} with TTL {ttl}s")
            return True
            
        except RedisError as e:
            logger.error(f"Error caching providers by type {provider_type}: {e}")
            return False

    # =============================================================================
    # PROVIDER CONFIGURATION CACHING
    # =============================================================================

    def get_provider_config(self, provider_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene configuración de provider desde cache"""
        try:
            cache_key = self._generate_cache_key(self.PROVIDER_CONFIG_PREFIX, provider_key)
            cached_data = self.redis.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting provider config {provider_key} from cache: {e}")
            return None

    def set_provider_config(self, provider_key: str, config: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Almacena configuración de provider en cache"""
        try:
            cache_key = self._generate_cache_key(self.PROVIDER_CONFIG_PREFIX, provider_key)
            ttl = ttl or self.CONFIG_TTL
            
            # Agregar hash para invalidación
            config_with_hash = {
                **config,
                '_config_hash': self._generate_hash(config),
                '_cached_at': datetime.utcnow().isoformat()
            }
            
            self.redis.setex(cache_key, ttl, json.dumps(config_with_hash))
            
            logger.debug(f"Cached config for provider {provider_key} with TTL {ttl}s")
            return True
            
        except RedisError as e:
            logger.error(f"Error caching provider config {provider_key}: {e}")
            return False

    # =============================================================================
    # PROVIDER HEALTH CACHING
    # =============================================================================

    def get_provider_health(self, provider_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene estado de salud de provider desde cache"""
        try:
            cache_key = self._generate_cache_key(self.PROVIDER_HEALTH_PREFIX, provider_key)
            cached_data = self.redis.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting provider health {provider_key} from cache: {e}")
            return None

    def set_provider_health(self, provider_key: str, health_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Almacena estado de salud de provider en cache"""
        try:
            cache_key = self._generate_cache_key(self.PROVIDER_HEALTH_PREFIX, provider_key)
            ttl = ttl or self.HEALTH_TTL
            
            # Agregar timestamp
            health_with_timestamp = {
                **health_data,
                '_health_checked_at': datetime.utcnow().isoformat()
            }
            
            self.redis.setex(cache_key, ttl, json.dumps(health_with_timestamp))
            
            logger.debug(f"Cached health for provider {provider_key} with TTL {ttl}s")
            return True
            
        except RedisError as e:
            logger.error(f"Error caching provider health {provider_key}: {e}")
            return False

    # =============================================================================
    # GROUP CACHING
    # =============================================================================

    def get_provider_group(self, group_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene grupo de providers desde cache"""
        try:
            cache_key = self._generate_cache_key(self.GROUP_KEY_PREFIX, group_key)
            cached_data = self.redis.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting provider group {group_key} from cache: {e}")
            return None

    def set_provider_group(self, group: ProviderGroup, ttl: Optional[int] = None) -> bool:
        """Almacena grupo de providers en cache"""
        try:
            cache_key = self._generate_cache_key(self.GROUP_KEY_PREFIX, group.group_key)
            group_data = group.to_dict()
            group_data['_cached_at'] = datetime.utcnow().isoformat()
            
            ttl = ttl or self.DEFAULT_TTL
            self.redis.setex(cache_key, ttl, json.dumps(group_data))
            
            logger.debug(f"Cached provider group {group.group_key} with TTL {ttl}s")
            return True
            
        except RedisError as e:
            logger.error(f"Error caching provider group {group.group_key}: {e}")
            return False

    def get_group_members(self, group_key: str) -> Optional[List[Dict[str, Any]]]:
        """Obtiene miembros de un grupo desde cache"""
        try:
            cache_key = self._generate_cache_key(self.GROUP_MEMBERS_KEY_PREFIX, group_key)
            cached_data = self.redis.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting group members {group_key} from cache: {e}")
            return None

    def set_group_members(self, group_key: str, members: List[Tuple[ProviderGroupMember, Provider]], ttl: Optional[int] = None) -> bool:
        """Almacena miembros de un grupo en cache"""
        try:
            cache_key = self._generate_cache_key(self.GROUP_MEMBERS_KEY_PREFIX, group_key)
            
            members_data = []
            for member, provider in members:
                member_data = member.to_dict()
                member_data['provider'] = self._serialize_provider(provider)
                members_data.append(member_data)
            
            ttl = ttl or self.DEFAULT_TTL
            self.redis.setex(cache_key, ttl, json.dumps(members_data))
            
            logger.debug(f"Cached {len(members_data)} group members for {group_key} with TTL {ttl}s")
            return True
            
        except RedisError as e:
            logger.error(f"Error caching group members {group_key}: {e}")
            return False

    # =============================================================================
    # CACHE INVALIDATION
    # =============================================================================

    def invalidate_provider(self, provider_key: str) -> bool:
        """Invalida cache de un provider específico"""
        try:
            keys_to_delete = []
            
            # Cache directo del provider
            provider_cache_key = self._generate_cache_key(self.PROVIDER_KEY_PREFIX, provider_key)
            keys_to_delete.append(provider_cache_key)
            
            # Config del provider
            config_cache_key = self._generate_cache_key(self.PROVIDER_CONFIG_PREFIX, provider_key)
            keys_to_delete.append(config_cache_key)
            
            # Health del provider
            health_cache_key = self._generate_cache_key(self.PROVIDER_HEALTH_PREFIX, provider_key)
            keys_to_delete.append(health_cache_key)
            
            # Listas agregadas que pueden incluir este provider
            keys_to_delete.extend([
                self.ACTIVE_PROVIDERS_KEY,
                self.PROVIDERS_LIST_KEY,
                "providers:type:*"  # Usar scan para encontrar estas claves
            ])
            
            # Eliminar claves
            if keys_to_delete:
                deleted_count = self.redis.delete(*[k for k in keys_to_delete if not k.endswith('*')])
                
                # Buscar y eliminar claves con pattern
                pattern_keys = self.redis.keys("providers:type:*")
                if pattern_keys:
                    self.redis.delete(*pattern_keys)
                
                logger.info(f"Invalidated {deleted_count + len(pattern_keys)} cache keys for provider {provider_key}")
            
            return True
            
        except RedisError as e:
            logger.error(f"Error invalidating cache for provider {provider_key}: {e}")
            return False

    def invalidate_group(self, group_key: str) -> bool:
        """Invalida cache de un grupo específico"""
        try:
            keys_to_delete = []
            
            # Cache del grupo
            group_cache_key = self._generate_cache_key(self.GROUP_KEY_PREFIX, group_key)
            keys_to_delete.append(group_cache_key)
            
            # Miembros del grupo
            members_cache_key = self._generate_cache_key(self.GROUP_MEMBERS_KEY_PREFIX, group_key)
            keys_to_delete.append(members_cache_key)
            
            # Eliminar claves
            if keys_to_delete:
                deleted_count = self.redis.delete(*keys_to_delete)
                logger.info(f"Invalidated {deleted_count} cache keys for group {group_key}")
            
            return True
            
        except RedisError as e:
            logger.error(f"Error invalidating cache for group {group_key}: {e}")
            return False

    def invalidate_all_providers(self) -> bool:
        """Invalida todo el cache de providers"""
        try:
            # Buscar todas las claves relacionadas con providers
            patterns = [
                "provider:*",
                "providers:*",
                "provider_config:*",
                "provider_health:*",
                "provider_group:*",
                "group_members:*"
            ]
            
            all_keys = []
            for pattern in patterns:
                keys = self.redis.keys(pattern)
                all_keys.extend(keys)
            
            if all_keys:
                deleted_count = self.redis.delete(*all_keys)
                logger.info(f"Invalidated all providers cache: {deleted_count} keys deleted")
            
            return True
            
        except RedisError as e:
            logger.error(f"Error invalidating all providers cache: {e}")
            return False

    # =============================================================================
    # CACHE STATISTICS
    # =============================================================================

    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache de providers"""
        try:
            stats = {
                'redis_connected': True,
                'cache_keys': {},
                'total_keys': 0,
                'memory_usage': None
            }
            
            # Contar claves por tipo
            patterns = {
                'providers': 'provider:*',
                'provider_lists': 'providers:*',
                'provider_configs': 'provider_config:*',
                'provider_health': 'provider_health:*',
                'provider_groups': 'provider_group:*',
                'group_members': 'group_members:*'
            }
            
            for category, pattern in patterns.items():
                keys = self.redis.keys(pattern)
                stats['cache_keys'][category] = len(keys)
                stats['total_keys'] += len(keys)
            
            # Información de memoria (si está disponible)
            try:
                info = self.redis.info('memory')
                stats['memory_usage'] = info.get('used_memory_human', 'unknown')
            except:
                pass
            
            return stats
            
        except RedisError as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                'redis_connected': False,
                'error': str(e)
            }

    def health_check(self) -> bool:
        """Verifica la salud de la conexión Redis"""
        try:
            self.redis.ping()
            return True
        except RedisError:
            return False


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Instancia global del cache
_providers_cache_instance: Optional[ProvidersCache] = None

def get_providers_cache() -> ProvidersCache:
    """Obtiene instancia singleton del cache de providers"""
    global _providers_cache_instance
    
    if _providers_cache_instance is None:
        _providers_cache_instance = ProvidersCache()
    
    return _providers_cache_instance

def init_providers_cache(redis_client: Optional[redis.Redis] = None) -> ProvidersCache:
    """Inicializa el cache de providers con un cliente Redis específico"""
    global _providers_cache_instance
    
    _providers_cache_instance = ProvidersCache(redis_client)
    return _providers_cache_instance