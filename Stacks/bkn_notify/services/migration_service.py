"""
Stacks/bkn_notify/services/migration_service.py
Migration Service - Migración de providers.yml a base de datos
Servicio para migrar configuración YAML existente hacia MySQL
"""

import logging
import json
import os
import yaml
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from utils.database import get_db_session
from models.provider_models import (
    Provider, ProviderGroup, ProviderGroupMember, ProviderHealthConfig,
    ProviderType, ProviderEnvironment, RoutingStrategy
)
from services.providers_cache import get_providers_cache
import constants

logger = logging.getLogger(__name__)


class MigrationService:
    """Servicio para migración de configuración YAML a base de datos"""

    def __init__(self):
        """Inicializa el servicio de migración"""
        self.providers_cache = get_providers_cache()
        self.migration_log = []
        self.errors = []
        self.warnings = []

    def _log_migration(self, level: str, message: str, provider_key: str = None):
        """Registra evento de migración"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level,
            'message': message,
            'provider_key': provider_key
        }
        
        self.migration_log.append(log_entry)
        
        if level == 'ERROR':
            self.errors.append(log_entry)
        elif level == 'WARNING':
            self.warnings.append(log_entry)
        
        # También log a Python logging
        getattr(logger, level.lower())(f"Migration: {message}")

    def _load_yaml_config(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Carga configuración desde archivo YAML"""
        try:
            if not os.path.exists(file_path):
                self._log_migration('ERROR', f"YAML file not found: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                
            if not config:
                self._log_migration('WARNING', f"Empty YAML file: {file_path}")
                return {}
            
            self._log_migration('INFO', f"Successfully loaded YAML: {file_path}")
            return config
            
        except yaml.YAMLError as e:
            self._log_migration('ERROR', f"YAML parsing error in {file_path}: {e}")
            return None
        except Exception as e:
            self._log_migration('ERROR', f"Error reading {file_path}: {e}")
            return None

    def _normalize_provider_type(self, provider_type: str) -> Optional[ProviderType]:
        """Normaliza tipo de proveedor desde YAML"""
        type_mapping = {
            'smtp': ProviderType.SMTP,
            'api': ProviderType.API,
            'webhook': ProviderType.WEBHOOK,
            'twilio': ProviderType.TWILIO,
            # Variaciones comunes
            'email': ProviderType.SMTP,
            'http': ProviderType.API,
            'rest': ProviderType.API
        }
        
        return type_mapping.get(provider_type.lower())

    def _extract_provider_credentials(self, config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Separa configuración técnica de credenciales sensibles"""
        
        # Campos que van en credentials_json (sensibles)
        credential_fields = {
            'username', 'password', 'api_key', 'secret_key', 'auth_token',
            'client_id', 'client_secret', 'private_key', 'certificate',
            'smtp_user', 'smtp_pass', 'smtp_password'
        }
        
        config_json = {}
        credentials_json = {}
        
        for key, value in config.items():
            if key.lower() in credential_fields or 'password' in key.lower() or 'secret' in key.lower():
                credentials_json[key] = value
            else:
                config_json[key] = value
        
        return config_json, credentials_json

    def _migrate_single_provider(self, provider_key: str, provider_config: Dict[str, Any], 
                                environment: str = 'production') -> Optional[Provider]:
        """Migra un proveedor individual desde configuración YAML"""
        
        try:
            # Validar campos requeridos
            if 'type' not in provider_config:
                self._log_migration('ERROR', f"Missing 'type' field in provider", provider_key)
                return None
            
            # Normalizar tipo
            provider_type = self._normalize_provider_type(provider_config['type'])
            if not provider_type:
                self._log_migration('ERROR', f"Invalid provider type: {provider_config['type']}", provider_key)
                return None
            
            # Extraer configuración y credenciales
            config_json, credentials_json = self._extract_provider_credentials(
                provider_config.get('config', {})
            )
            
            # Crear objeto Provider
            provider_data = {
                'provider_key': provider_key,
                'name': provider_config.get('name', provider_key.replace('_', ' ').title()),
                'description': provider_config.get('description', f'Migrated from YAML - {provider_key}'),
                'provider_type': provider_type,
                'enabled': provider_config.get('enabled', True),
                'priority': provider_config.get('priority', 100),
                'weight': provider_config.get('weight', 10),
                'max_retries': provider_config.get('max_retries', 3),
                'timeout_seconds': provider_config.get('timeout', 30),
                'rate_limit_per_minute': provider_config.get('rate_limit', 60),
                'config_json': config_json,
                'credentials_json': credentials_json if credentials_json else None,
                'health_check_enabled': provider_config.get('health_check', {}).get('enabled', True),
                'health_check_url': provider_config.get('health_check', {}).get('url'),
                'health_check_interval_minutes': provider_config.get('health_check', {}).get('interval', 5),
                'environment': ProviderEnvironment(environment),
                'created_by': 'migration_service',
                'updated_by': 'migration_service'
            }
            
            # Crear provider en base de datos
            with get_db_session() as db:
                # Verificar si ya existe
                existing = db.query(Provider).filter(Provider.provider_key == provider_key).first()
                if existing:
                    self._log_migration('WARNING', f"Provider already exists, skipping", provider_key)
                    return existing
                
                # Crear nuevo provider
                provider = Provider(**provider_data)
                db.add(provider)
                db.flush()  # Para obtener el ID sin hacer commit
                
                # Crear configuración de health check si está especificada
                if provider_config.get('health_check'):
                    health_config = self._create_health_config(provider.id, provider_config['health_check'])
                    if health_config:
                        db.add(health_config)
                
                db.commit()
                db.refresh(provider)
                
                self._log_migration('INFO', f"Successfully migrated provider", provider_key)
                return provider
                
        except IntegrityError as e:
            self._log_migration('ERROR', f"Database integrity error: {e}", provider_key)
            return None
        except SQLAlchemyError as e:
            self._log_migration('ERROR', f"Database error: {e}", provider_key)
            return None
        except Exception as e:
            self._log_migration('ERROR', f"Unexpected error migrating provider: {e}", provider_key)
            return None

    def _create_health_config(self, provider_id: int, health_config: Dict[str, Any]) -> Optional[ProviderHealthConfig]:
        """Crea configuración de health check para un provider"""
        try:
            config_data = {
                'provider_id': provider_id,
                'enabled': health_config.get('enabled', True),
                'check_interval_minutes': health_config.get('interval', 5),
                'timeout_seconds': health_config.get('timeout', 30),
                'health_check_url': health_config.get('url'),
                'expected_status_code': health_config.get('expected_status', 200),
                'consecutive_failures_threshold': health_config.get('failure_threshold', 3),
                'consecutive_successes_threshold': health_config.get('success_threshold', 2),
                'max_response_time_ms': health_config.get('max_response_time', 5000),
                'alert_on_failure': health_config.get('alert_on_failure', True),
                'alert_on_recovery': health_config.get('alert_on_recovery', True),
                'created_by': 'migration_service'
            }
            
            return ProviderHealthConfig(**config_data)
            
        except Exception as e:
            logger.error(f"Error creating health config for provider {provider_id}: {e}")
            return None

    def _migrate_provider_groups(self, groups_config: Dict[str, Any]) -> List[ProviderGroup]:
        """Migra grupos de proveedores desde configuración YAML"""
        
        migrated_groups = []
        
        try:
            with get_db_session() as db:
                for group_key, group_config in groups_config.items():
                    try:
                        # Verificar si ya existe
                        existing = db.query(ProviderGroup).filter(ProviderGroup.group_key == group_key).first()
                        if existing:
                            self._log_migration('WARNING', f"Group already exists: {group_key}")
                            migrated_groups.append(existing)
                            continue
                        
                        # Mapear estrategia de routing
                        strategy_mapping = {
                            'priority': RoutingStrategy.PRIORITY,
                            'round_robin': RoutingStrategy.ROUND_ROBIN,
                            'failover': RoutingStrategy.FAILOVER,
                            'load_balance': RoutingStrategy.LOAD_BALANCE,
                            'random': RoutingStrategy.RANDOM
                        }
                        
                        routing_strategy = strategy_mapping.get(
                            group_config.get('strategy', 'priority'), 
                            RoutingStrategy.PRIORITY
                        )
                        
                        # Crear grupo
                        group_data = {
                            'group_key': group_key,
                            'name': group_config.get('name', group_key.replace('_', ' ').title()),
                            'description': group_config.get('description', f'Migrated from YAML - {group_key}'),
                            'routing_strategy': routing_strategy,
                            'failover_enabled': group_config.get('failover_enabled', True),
                            'failover_timeout_seconds': group_config.get('failover_timeout', 30),
                            'max_group_retries': group_config.get('max_retries', 2),
                            'retry_delay_seconds': group_config.get('retry_delay', 5),
                            'enabled': group_config.get('enabled', True),
                            'environment': ProviderEnvironment.PRODUCTION,
                            'created_by': 'migration_service'
                        }
                        
                        group = ProviderGroup(**group_data)
                        db.add(group)
                        db.flush()
                        
                        # Agregar miembros al grupo
                        members = group_config.get('members', [])
                        for member_config in members:
                            if isinstance(member_config, str):
                                provider_key = member_config
                                member_priority = 100
                                member_weight = 10
                            elif isinstance(member_config, dict):
                                provider_key = member_config.get('provider')
                                member_priority = member_config.get('priority', 100)
                                member_weight = member_config.get('weight', 10)
                            else:
                                continue
                            
                            # Buscar provider
                            provider = db.query(Provider).filter(Provider.provider_key == provider_key).first()
                            if provider:
                                member = ProviderGroupMember(
                                    group_id=group.id,
                                    provider_id=provider.id,
                                    priority=member_priority,
                                    weight=member_weight,
                                    enabled=True,
                                    added_by='migration_service'
                                )
                                db.add(member)
                            else:
                                self._log_migration('WARNING', f"Provider {provider_key} not found for group {group_key}")
                        
                        migrated_groups.append(group)
                        self._log_migration('INFO', f"Successfully migrated group: {group_key}")
                        
                    except Exception as e:
                        self._log_migration('ERROR', f"Error migrating group {group_key}: {e}")
                        continue
                
                db.commit()
                
        except Exception as e:
            self._log_migration('ERROR', f"Error migrating provider groups: {e}")
        
        return migrated_groups

    def migrate_from_yaml(self, providers_file: str, groups_file: str = None, 
                         environment: str = 'production', dry_run: bool = False) -> Dict[str, Any]:
        """
        Migra configuración completa desde archivos YAML
        
        Args:
            providers_file: Path al archivo providers.yml
            groups_file: Path al archivo de grupos (opcional)
            environment: Ambiente target ('production', 'staging', 'development')
            dry_run: Si True, simula la migración sin hacer cambios
            
        Returns:
            Dict con resultados de la migración
        """
        
        self._log_migration('INFO', f"Starting migration from YAML - Environment: {environment}")
        
        if dry_run:
            self._log_migration('INFO', "DRY RUN MODE - No changes will be made")
        
        migration_results = {
            'started_at': datetime.utcnow().isoformat(),
            'dry_run': dry_run,
            'environment': environment,
            'providers': {'migrated': 0, 'skipped': 0, 'errors': 0},
            'groups': {'migrated': 0, 'skipped': 0, 'errors': 0},
            'errors': [],
            'warnings': [],
            'migration_log': []
        }
        
        try:
            # Cargar configuración de providers
            providers_config = self._load_yaml_config(providers_file)
            if not providers_config:
                return migration_results
            
            # Migrar providers individuales
            migrated_providers = []
            for provider_key, provider_config in providers_config.items():
                if not dry_run:
                    provider = self._migrate_single_provider(provider_key, provider_config, environment)
                    if provider:
                        migrated_providers.append(provider)
                        migration_results['providers']['migrated'] += 1
                    else:
                        migration_results['providers']['errors'] += 1
                else:
                    # En dry run, solo validar
                    self._log_migration('INFO', f"DRY RUN: Would migrate provider {provider_key}")
                    migration_results['providers']['migrated'] += 1
            
            # Migrar grupos si se especifica archivo
            if groups_file and os.path.exists(groups_file):
                groups_config = self._load_yaml_config(groups_file)
                if groups_config and not dry_run:
                    migrated_groups = self._migrate_provider_groups(groups_config)
                    migration_results['groups']['migrated'] = len(migrated_groups)
                elif dry_run and groups_config:
                    for group_key in groups_config.keys():
                        self._log_migration('INFO', f"DRY RUN: Would migrate group {group_key}")
                        migration_results['groups']['migrated'] += 1
            
            # Invalidar cache si no es dry run
            if not dry_run:
                self.providers_cache.invalidate_all_providers()
                self._log_migration('INFO', "Invalidated providers cache after migration")
            
            migration_results['completed_at'] = datetime.utcnow().isoformat()
            migration_results['success'] = len(self.errors) == 0
            
        except Exception as e:
            self._log_migration('ERROR', f"Fatal error during migration: {e}")
            migration_results['success'] = False
        
        finally:
            # Agregar logs al resultado
            migration_results['errors'] = self.errors
            migration_results['warnings'] = self.warnings
            migration_results['migration_log'] = self.migration_log
        
        return migration_results

    def validate_yaml_config(self, providers_file: str) -> Dict[str, Any]:
        """
        Valida configuración YAML sin migrar
        
        Returns:
            Dict con resultados de validación
        """
        
        validation_results = {
            'valid': True,
            'providers_count': 0,
            'validation_errors': [],
            'validation_warnings': [],
            'provider_details': {}
        }
        
        try:
            providers_config = self._load_yaml_config(providers_file)
            if not providers_config:
                validation_results['valid'] = False
                return validation_results
            
            validation_results['providers_count'] = len(providers_config)
            
            for provider_key, provider_config in providers_config.items():
                provider_validation = {
                    'valid': True,
                    'errors': [],
                    'warnings': []
                }
                
                # Validar campos requeridos
                if 'type' not in provider_config:
                    provider_validation['errors'].append("Missing required field: 'type'")
                    provider_validation['valid'] = False
                
                # Validar tipo de proveedor
                if 'type' in provider_config:
                    normalized_type = self._normalize_provider_type(provider_config['type'])
                    if not normalized_type:
                        provider_validation['errors'].append(f"Invalid provider type: {provider_config['type']}")
                        provider_validation['valid'] = False
                
                # Validar configuración específica
                if 'config' not in provider_config:
                    provider_validation['warnings'].append("No 'config' section found")
                
                validation_results['provider_details'][provider_key] = provider_validation
                
                if not provider_validation['valid']:
                    validation_results['valid'] = False
                    validation_results['validation_errors'].extend(provider_validation['errors'])
                
                validation_results['validation_warnings'].extend(provider_validation['warnings'])
        
        except Exception as e:
            validation_results['valid'] = False
            validation_results['validation_errors'].append(f"Validation error: {e}")
        
        return validation_results

    def export_to_yaml(self, output_file: str, environment: str = 'production') -> bool:
        """
        Exporta configuración actual de base de datos a YAML
        Útil para backup antes de modificaciones
        """
        
        try:
            export_data = {}
            
            with get_db_session() as db:
                # Obtener todos los providers del ambiente
                providers = db.query(Provider).filter(Provider.environment == environment).all()
                
                for provider in providers:
                    provider_config = {
                        'name': provider.name,
                        'description': provider.description,
                        'type': provider.provider_type.value,
                        'enabled': provider.enabled,
                        'priority': provider.priority,
                        'weight': provider.weight,
                        'max_retries': provider.max_retries,
                        'timeout': provider.timeout_seconds,
                        'rate_limit': provider.rate_limit_per_minute,
                        'config': provider.config_json or {}
                    }
                    
                    # Agregar health check config si existe
                    if provider.health_config:
                        provider_config['health_check'] = {
                            'enabled': provider.health_config.enabled,
                            'interval': provider.health_config.check_interval_minutes,
                            'timeout': provider.health_config.timeout_seconds,
                            'url': provider.health_config.health_check_url
                        }
                    
                    export_data[provider.provider_key] = provider_config
            
            # Escribir YAML
            with open(output_file, 'w', encoding='utf-8') as file:
                yaml.dump(export_data, file, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Successfully exported {len(export_data)} providers to {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to YAML: {e}")
            return False

    def get_migration_status(self) -> Dict[str, Any]:
        """Obtiene estado actual de la migración"""
        
        try:
            with get_db_session() as db:
                total_providers = db.query(Provider).count()
                enabled_providers = db.query(Provider).filter(Provider.enabled == True).count()
                healthy_providers = db.query(Provider).filter(
                    Provider.enabled == True, 
                    Provider.is_healthy == True
                ).count()
                
                return {
                    'database_ready': True,
                    'total_providers': total_providers,
                    'enabled_providers': enabled_providers,
                    'healthy_providers': healthy_providers,
                    'cache_status': self.providers_cache.health_check(),
                    'last_check': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return {
                'database_ready': False,
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }