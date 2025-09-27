"""
Stacks/bkn_notify/utils/providers_loader.py
Providers Loader - Cargador unificado YAML/Database con fallback
Implementa dual mode con cache y fallback automático
"""

import os
import logging
from typing import List, Dict, Any, Optional
from enum import Enum

import redis

from repositories.providers_repository import ProvidersRepository
from repositories.provider_groups_repository import ProviderGroupsRepository
from repositories.providers_cache import ProvidersCache

logger = logging.getLogger(__name__)


class LoaderMode(str, Enum):
    """Modos de carga de providers"""
    DATABASE = "database"
    YAML = "yaml"
    AUTO = "auto"


class ProvidersLoader:
    """
    Loader unificado para providers con soporte dual mode
    Maneja carga desde BD o YAML con fallback automático
    """
    
    def __init__(
        self, 
        redis_client: Optional[redis.Redis] = None,
        cache_ttl: int = 300,
        use_database: bool = False
    ):
        """
        Inicializa loader con configuración
        
        Args:
            redis_client: Cliente Redis para cache (opcional)
            cache_ttl: TTL del cache en segundos
            use_database: Si True, usa BD; si False, usa YAML
        """
        self.use_database = use_database
        self.cache = ProvidersCache(redis_client, ttl=cache_ttl)
        self.mode = LoaderMode.DATABASE if use_database else LoaderMode.YAML
        
        # Environment actual
        self.environment = os.getenv("APP_ENV", "production")
        
        logger.info(f"ProvidersLoader initialized in {self.mode.value} mode")
    
    
    # ==========================================================================
    # MÉTODOS PRINCIPALES - INTERFACE UNIFICADA
    # ==========================================================================
    
    def get_all_providers(
        self, 
        use_cache: bool = True,
        environment: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene todos los providers (BD o YAML según configuración)
        
        Args:
            use_cache: Si usa cache Redis
            environment: Filtrar por ambiente
            
        Returns:
            Lista de providers
        """
        env = environment or self.environment
        
        # Intentar cache primero
        if use_cache:
            cached = self.cache.get_all_providers(env)
            if cached is not None:
                logger.debug(f"Providers loaded from cache ({len(cached)} items)")
                return cached
        
        # Cargar según modo configurado
        if self.mode == LoaderMode.DATABASE:
            providers = self._load_from_database(env)
            
            # Fallback a YAML si BD falla
            if providers is None or len(providers) == 0:
                logger.warning("Database load failed, falling back to YAML")
                providers = self._load_from_yaml(env)
        else:
            providers = self._load_from_yaml(env)
        
        # Guardar en cache si está habilitado
        if use_cache and providers:
            self.cache.set_all_providers(providers, env)
        
        logger.info(f"Loaded {len(providers)} providers from {self.mode.value}")
        return providers
    
    
    def get_active_providers(
        self, 
        use_cache: bool = True,
        environment: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene solo providers activos y saludables
        
        Args:
            use_cache: Si usa cache Redis
            environment: Filtrar por ambiente
            
        Returns:
            Lista de providers activos
        """
        env = environment or self.environment
        
        # Intentar cache primero
        if use_cache:
            cached = self.cache.get_active_providers(env)
            if cached is not None:
                logger.debug(f"Active providers loaded from cache ({len(cached)} items)")
                return cached
        
        # Cargar según modo
        if self.mode == LoaderMode.DATABASE:
            providers = self._load_active_from_database(env)
            
            # Fallback a YAML
            if providers is None:
                logger.warning("Database load failed, falling back to YAML")
                providers = self._load_active_from_yaml(env)
        else:
            providers = self._load_active_from_yaml(env)
        
        # Guardar en cache
        if use_cache and providers:
            self.cache.set_active_providers(providers, env)
        
        logger.info(f"Loaded {len(providers)} active providers from {self.mode.value}")
        return providers
    
    
    def get_provider_by_key(
        self, 
        provider_key: str,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene provider específico por clave
        
        Args:
            provider_key: Identificador único del provider
            use_cache: Si usa cache Redis
            
        Returns:
            Provider como diccionario o None
        """
        # Intentar cache primero
        if use_cache:
            cached = self.cache.get_provider_by_key(provider_key)
            if cached is not None:
                logger.debug(f"Provider '{provider_key}' loaded from cache")
                return cached
        
        # Cargar según modo
        if self.mode == LoaderMode.DATABASE:
            provider = ProvidersRepository.get_provider_by_key(provider_key)
            
            # Fallback a YAML
            if provider is None:
                logger.warning(f"Provider '{provider_key}' not found in DB, trying YAML")
                provider = self._get_provider_from_yaml(provider_key)
        else:
            provider = self._get_provider_from_yaml(provider_key)
        
        # Guardar en cache
        if use_cache and provider:
            self.cache.set_provider(provider)
        
        return provider
    
    
    def get_providers_by_type(
        self, 
        provider_type: str,
        only_active: bool = False,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Obtiene providers por tipo
        
        Args:
            provider_type: Tipo de provider (smtp, api, webhook, twilio)
            only_active: Si True, solo activos
            use_cache: Si usa cache Redis
            
        Returns:
            Lista de providers del tipo especificado
        """
        # Intentar cache primero
        if use_cache:
            cached = self.cache.get_providers_by_type(provider_type, only_active)
            if cached is not None:
                logger.debug(f"Providers type '{provider_type}' loaded from cache")
                return cached
        
        # Cargar según modo
        if self.mode == LoaderMode.DATABASE:
            providers = ProvidersRepository.get_providers_by_type(provider_type, only_active)
            
            # Fallback a YAML
            if providers is None or len(providers) == 0:
                logger.warning(f"No providers type '{provider_type}' in DB, trying YAML")
                providers = self._get_providers_by_type_from_yaml(provider_type, only_active)
        else:
            providers = self._get_providers_by_type_from_yaml(provider_type, only_active)
        
        # Guardar en cache
        if use_cache and providers:
            self.cache.set_providers_by_type(provider_type, providers, only_active)
        
        return providers
    
    
    # ==========================================================================
    # MÉTODOS PARA GRUPOS
    # ==========================================================================
    
    def get_group_with_providers(
        self, 
        group_key: str,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene grupo completo con providers para routing
        
        Args:
            group_key: Identificador único del grupo
            use_cache: Si usa cache Redis
            
        Returns:
            Grupo con lista de providers activos
        """
        # Intentar cache primero
        if use_cache:
            cached = self.cache.get_group_with_providers(group_key)
            if cached is not None:
                logger.debug(f"Group '{group_key}' with providers loaded from cache")
                return cached
        
        # Solo disponible en modo database
        if self.mode == LoaderMode.DATABASE:
            group_data = ProviderGroupsRepository.get_group_with_active_providers(group_key)
            
            if group_data and use_cache:
                self.cache.set_group_with_providers(group_key, group_data)
            
            return group_data
        else:
            logger.warning(f"Groups not supported in YAML mode")
            return None
    
    
    # ==========================================================================
    # CARGA DESDE BASE DE DATOS
    # ==========================================================================
    
    def _load_from_database(self, environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """Carga providers desde base de datos"""
        try:
            providers = ProvidersRepository.get_all_providers(environment)
            logger.debug(f"Loaded {len(providers)} providers from database")
            return providers
        except Exception as e:
            logger.error(f"Error loading providers from database: {e}")
            return []
    
    
    def _load_active_from_database(self, environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """Carga providers activos desde base de datos"""
        try:
            providers = ProvidersRepository.get_active_providers(environment)
            logger.debug(f"Loaded {len(providers)} active providers from database")
            return providers
        except Exception as e:
            logger.error(f"Error loading active providers from database: {e}")
            return []
    
    
    # ==========================================================================
    # CARGA DESDE YAML (FALLBACK)
    # ==========================================================================
    
    def _load_from_yaml(self, environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Carga providers desde YAML (legacy)
        Usa config_loader existente
        """
        try:
            # FIX: Usar path absoluto
            import os
            yaml_path = os.path.join("/app/Config", "providers.yml")
            
            from utils.config_loader import load_yaml_file
            yaml_config = load_yaml_file(yaml_path, resolve_vars=True)

            if not yaml_config:
                logger.error("Failed to load providers.yml")
                return []
            
            # Convertir formato YAML a formato estándar
            providers = []
            for key, config in yaml_config.items():
                if isinstance(config, dict):
                    provider = {
                        "provider_key": key,
                        "name": config.get("name", key),
                        "provider_type": config.get("type", "smtp"),
                        "enabled": config.get("enabled", True),
                        "priority": config.get("priority", 100),
                        "config_json": {
                            "host": config.get("host"),
                            "port": config.get("port"),
                            "use_tls": config.get("use_tls", False),
                            "use_ssl": config.get("use_ssl", False)
                        },
                        "credentials_json": {
                            "username": config.get("username"),
                            "password": config.get("password")
                        },
                        "is_healthy": True,
                        "environment": environment or "production"
                    }
                    providers.append(provider)
            
            logger.debug(f"Loaded {len(providers)} providers from YAML")
            return providers
            
        except Exception as e:
            logger.error(f"Error loading providers from YAML: {e}")
            return []
    
    
    def _load_active_from_yaml(self, environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """Carga providers activos desde YAML"""
        all_providers = self._load_from_yaml(environment)
        return [p for p in all_providers if p.get("enabled", True)]
    
    
    def _get_provider_from_yaml(self, provider_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene provider específico desde YAML"""
        all_providers = self._load_from_yaml()
        for provider in all_providers:
            if provider.get("provider_key") == provider_key:
                return provider
        return None
    
    
    def _get_providers_by_type_from_yaml(
        self, 
        provider_type: str, 
        only_active: bool = False
    ) -> List[Dict[str, Any]]:
        """Obtiene providers por tipo desde YAML"""
        all_providers = self._load_from_yaml()
        filtered = [
            p for p in all_providers 
            if p.get("provider_type") == provider_type
        ]
        
        if only_active:
            filtered = [p for p in filtered if p.get("enabled", True)]
        
        return filtered
    
    
    # ==========================================================================
    # INVALIDACIÓN DE CACHE
    # ==========================================================================
    
    def invalidate_provider_cache(self, provider_key: str) -> bool:
        """Invalida cache de un provider específico"""
        return self.cache.invalidate_provider(provider_key)
    
    
    def invalidate_all_providers_cache(self) -> bool:
        """Invalida todo el cache de providers"""
        return self.cache.invalidate_all_providers()
    
    
    def invalidate_group_cache(self, group_key: str) -> bool:
        """Invalida cache de un grupo específico"""
        return self.cache.invalidate_group(group_key)
    
    
    def invalidate_all_groups_cache(self) -> bool:
        """Invalida todo el cache de grupos"""
        return self.cache.invalidate_all_groups()
    
    
    # ==========================================================================
    # UTILIDADES
    # ==========================================================================
    
    def get_loader_info(self) -> Dict[str, Any]:
        """Obtiene información del loader"""
        return {
            "mode": self.mode.value,
            "database_enabled": self.use_database,
            "cache_enabled": self.cache.enabled,
            "environment": self.environment,
            "cache_stats": self.cache.get_cache_stats() if self.cache.enabled else None
        }
    
    
    def switch_mode(self, use_database: bool) -> bool:
        """
        Cambia el modo de carga (runtime)
        
        Args:
            use_database: True para BD, False para YAML
            
        Returns:
            True si cambió correctamente
        """
        try:
            old_mode = self.mode
            self.use_database = use_database
            self.mode = LoaderMode.DATABASE if use_database else LoaderMode.YAML
            
            # Invalidar todo el cache al cambiar de modo
            self.invalidate_all_providers_cache()
            self.invalidate_all_groups_cache()
            
            logger.info(f"Loader mode switched from {old_mode.value} to {self.mode.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error switching loader mode: {e}")
            return False
    
    
    def health_check(self) -> Dict[str, Any]:
        """Health check del loader"""
        health = {
            "loader_mode": self.mode.value,
            "cache_available": self.cache.ping() if self.cache.enabled else False
        }
        
        # Test de carga
        if self.mode == LoaderMode.DATABASE:
            try:
                providers = ProvidersRepository.get_all_providers()
                health["database_available"] = True
                health["providers_count"] = len(providers)
            except Exception as e:
                health["database_available"] = False
                health["database_error"] = str(e)
        else:
            try:
                providers = self._load_from_yaml()
                health["yaml_available"] = True
                health["providers_count"] = len(providers)
            except Exception as e:
                health["yaml_available"] = False
                health["yaml_error"] = str(e)
        
        return health