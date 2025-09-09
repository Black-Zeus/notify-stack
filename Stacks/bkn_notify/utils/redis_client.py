"""
Redis client utility
Manejo centralizado de conexiones Redis para cache y broker
"""

import redis.asyncio as redis
import logging
from typing import Optional

from constants import REDIS_URL, REDIS_TTL_DEFAULT

# Cliente Redis global
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """
    Obtiene cliente Redis singleton
    Crea conexión si no existe
    """
    global _redis_client
    
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            
            # Verificar conexión
            await _redis_client.ping()
            logging.info("Redis client initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize Redis client: {e}")
            raise
    
    return _redis_client


async def close_redis_client():
    """
    Cierra conexión Redis
    Útil para cleanup en shutdown
    """
    global _redis_client
    
    if _redis_client:
        try:
            await _redis_client.close()
            _redis_client = None
            logging.info("Redis client closed")
        except Exception as e:
            logging.error(f"Error closing Redis client: {e}")


class RedisHelper:
    """
    Helper class con operaciones Redis comunes
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def set_with_ttl(self, key: str, value: str, ttl: int = REDIS_TTL_DEFAULT) -> bool:
        """Establece clave con TTL"""
        try:
            return await self.redis.setex(key, ttl, value)
        except Exception as e:
            logging.error(f"Redis SET failed for key {key}: {e}")
            return False
    
    async def get_json(self, key: str) -> Optional[dict]:
        """Obtiene y deserializa JSON"""
        try:
            data = await self.redis.get(key)
            if data:
                import json
                return json.loads(data)
            return None
        except Exception as e:
            logging.error(f"Redis GET JSON failed for key {key}: {e}")
            return None
    
    async def set_json(self, key: str, data: dict, ttl: int = REDIS_TTL_DEFAULT) -> bool:
        """Serializa y guarda JSON"""
        try:
            import json
            return await self.redis.setex(key, ttl, json.dumps(data))
        except Exception as e:
            logging.error(f"Redis SET JSON failed for key {key}: {e}")
            return False
    
    async def push_log(self, log_key: str, log_entry: dict, max_entries: int = 1000) -> bool:
        """
        Agrega entrada de log y mantiene límite
        Usa lista Redis con LPUSH + LTRIM
        """
        try:
            import json
            
            # Agregar nueva entrada al inicio
            await self.redis.lpush(log_key, json.dumps(log_entry))
            
            # Mantener solo las últimas max_entries
            await self.redis.ltrim(log_key, 0, max_entries - 1)
            
            return True
        except Exception as e:
            logging.error(f"Redis push log failed for key {log_key}: {e}")
            return False
    
    async def exists_key(self, key: str) -> bool:
        """Verifica si existe clave"""
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logging.error(f"Redis EXISTS failed for key {key}: {e}")
            return False
    
    async def delete_key(self, key: str) -> bool:
        """Elimina clave"""
        try:
            return await self.redis.delete(key) > 0
        except Exception as e:
            logging.error(f"Redis DELETE failed for key {key}: {e}")
            return False
    
    async def increment_counter(self, key: str, ttl: int = REDIS_TTL_DEFAULT) -> int:
        """
        Incrementa contador con TTL
        Útil para rate limiting
        """
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except Exception as e:
            logging.error(f"Redis INCR failed for key {key}: {e}")
            return 0


async def get_redis_helper() -> RedisHelper:
    """
    Obtiene helper Redis con cliente inicializado
    """
    client = await get_redis_client()
    return RedisHelper(client)