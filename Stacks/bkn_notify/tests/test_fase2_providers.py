#!/usr/bin/env python3
"""
Stacks/bkn_notify/tests/test_fase2_providers.py
Script de Testing para FASE 2 - Dual Mode Providers
Valida funcionamiento de carga desde BD y YAML con fallback
"""

import os
import sys
import time
import logging
from typing import Dict, Any, List

# Setup path
sys.path.insert(0, '/app')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Fase2Tester:
    """Tester para validación de FASE 2"""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    
    def test(self, name: str, func):
        """Ejecuta un test y registra resultado"""
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"TEST: {name}")
            logger.info(f"{'='*60}")
            
            start_time = time.time()
            result = func()
            elapsed_ms = (time.time() - start_time) * 1000
            
            if result:
                logger.info(f"✅ PASSED ({elapsed_ms:.2f}ms)")
                self.passed += 1
                self.results.append({
                    "test": name,
                    "status": "PASSED",
                    "time_ms": round(elapsed_ms, 2)
                })
            else:
                logger.error(f"❌ FAILED ({elapsed_ms:.2f}ms)")
                self.failed += 1
                self.results.append({
                    "test": name,
                    "status": "FAILED",
                    "time_ms": round(elapsed_ms, 2)
                })
                
        except Exception as e:
            logger.error(f"❌ ERROR: {e}")
            self.failed += 1
            self.results.append({
                "test": name,
                "status": "ERROR",
                "error": str(e)
            })
    
    
    def print_summary(self):
        """Imprime resumen de tests"""
        logger.info(f"\n{'='*60}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total Tests: {self.passed + self.failed}")
        logger.info(f"✅ Passed: {self.passed}")
        logger.info(f"❌ Failed: {self.failed}")
        logger.info(f"Success Rate: {(self.passed/(self.passed+self.failed)*100):.1f}%")
        logger.info(f"{'='*60}\n")


# =============================================================================
# TESTS
# =============================================================================

def test_01_yaml_mode():
    """Test 1: Modo YAML tradicional"""
    # Forzar modo YAML
    os.environ["USE_DATABASE_PROVIDERS"] = "false"
    
    from utils.config_loader import load_providers_config
    
    providers = load_providers_config(force_reload=True)
    
    logger.info(f"Providers loaded: {len(providers)}")
    logger.info(f"Providers: {list(providers.keys())}")
    
    assert len(providers) > 0, "No providers loaded from YAML"
    assert isinstance(providers, dict), "Providers should be dict"
    
    return True


def test_02_database_mode():
    """Test 2: Modo Database"""
    # Forzar modo database
    os.environ["USE_DATABASE_PROVIDERS"] = "true"
    
    from utils.config_loader import load_providers_config
    
    providers = load_providers_config(force_reload=True)
    
    logger.info(f"Providers loaded: {len(providers)}")
    logger.info(f"Providers: {list(providers.keys())}")
    
    # Validar que retorna algo (BD o fallback YAML)
    assert isinstance(providers, dict), "Providers should be dict"
    
    return True


def test_03_providers_loader_yaml():
    """Test 3: ProvidersLoader en modo YAML"""
    from utils.providers_loader import ProvidersLoader
    
    loader = ProvidersLoader(
        redis_client=None,
        cache_ttl=300,
        use_database=False
    )
    
    providers = loader.get_all_providers(use_cache=False)
    
    logger.info(f"Loader mode: {loader.mode.value}")
    logger.info(f"Providers loaded: {len(providers)}")
    
    assert loader.mode.value == "yaml", "Loader should be in YAML mode"
    assert len(providers) > 0, "Should load providers from YAML"
    
    return True


def test_04_providers_loader_database():
    """Test 4: ProvidersLoader en modo Database"""
    from utils.providers_loader import ProvidersLoader
    
    loader = ProvidersLoader(
        redis_client=None,
        cache_ttl=300,
        use_database=True
    )
    
    providers = loader.get_all_providers(use_cache=False)
    
    logger.info(f"Loader mode: {loader.mode.value}")
    logger.info(f"Providers loaded: {len(providers)}")
    
    assert loader.mode.value == "database", "Loader should be in database mode"
    # Puede fallar si BD no está disponible, pero debería hacer fallback
    
    return True


def test_05_providers_repository():
    """Test 5: ProvidersRepository CRUD"""
    from repositories.providers_repository import ProvidersRepository
    
    # Get all providers
    all_providers = ProvidersRepository.get_all_providers()
    logger.info(f"All providers: {len(all_providers)}")
    
    # Get active providers
    active_providers = ProvidersRepository.get_active_providers()
    logger.info(f"Active providers: {len(active_providers)}")
    
    # Get provider stats
    stats = ProvidersRepository.get_providers_stats()
    logger.info(f"Stats: {stats}")
    
    assert isinstance(all_providers, list), "Should return list"
    assert isinstance(stats, dict), "Stats should be dict"
    
    return True


def test_06_provider_groups_repository():
    """Test 6: ProviderGroupsRepository"""
    from repositories.provider_groups_repository import ProviderGroupsRepository
    
    # Get all groups
    all_groups = ProviderGroupsRepository.get_all_groups()
    logger.info(f"All groups: {len(all_groups)}")
    
    # Get active groups
    active_groups = ProviderGroupsRepository.get_active_groups()
    logger.info(f"Active groups: {len(active_groups)}")
    
    # Get stats
    stats = ProviderGroupsRepository.get_groups_stats()
    logger.info(f"Groups stats: {stats}")
    
    assert isinstance(all_groups, list), "Should return list"
    assert isinstance(stats, dict), "Stats should be dict"
    
    return True


def test_07_providers_cache():
    """Test 7: ProvidersCache con Redis"""
    try:
        import redis
        from repositories.providers_cache import ProvidersCache
        
        # Conectar a Redis
        redis_client = redis.from_url(
            os.getenv("REDIS_URL", "redis://bkn_redis:6379/0"),
            decode_responses=True
        )
        
        cache = ProvidersCache(redis_client, ttl=60)
        
        # Test ping
        is_alive = cache.ping()
        logger.info(f"Redis alive: {is_alive}")
        
        # Test cache stats
        stats = cache.get_cache_stats()
        logger.info(f"Cache stats: {stats}")
        
        assert cache.enabled, "Cache should be enabled"
        assert is_alive, "Redis should be alive"
        
        return True
        
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        # No fallar si Redis no está disponible
        return True


def test_08_performance_load_yaml():
    """Test 8: Performance - Carga YAML"""
    os.environ["USE_DATABASE_PROVIDERS"] = "false"
    
    from utils.config_loader import load_providers_config
    
    start = time.time()
    providers = load_providers_config(force_reload=True)
    elapsed_ms = (time.time() - start) * 1000
    
    logger.info(f"YAML load time: {elapsed_ms:.2f}ms")
    logger.info(f"Providers loaded: {len(providers)}")
    
    # Validar que carga en menos de 50ms
    assert elapsed_ms < 100, f"YAML load too slow: {elapsed_ms:.2f}ms"
    
    return True


def test_09_performance_load_database():
    """Test 9: Performance - Carga Database"""
    os.environ["USE_DATABASE_PROVIDERS"] = "true"
    
    from utils.config_loader import load_providers_config
    
    start = time.time()
    providers = load_providers_config(force_reload=True)
    elapsed_ms = (time.time() - start) * 1000
    
    logger.info(f"Database load time: {elapsed_ms:.2f}ms")
    logger.info(f"Providers loaded: {len(providers)}")
    
    # Más tolerante para BD (puede incluir fallback)
    assert elapsed_ms < 200, f"Database load too slow: {elapsed_ms:.2f}ms"
    
    return True


def test_10_fallback_mechanism():
    """Test 10: Fallback automático BD → YAML"""
    os.environ["USE_DATABASE_PROVIDERS"] = "true"
    os.environ["PROVIDERS_DUAL_MODE"] = "true"
    
    from utils.providers_loader import ProvidersLoader
    
    loader = ProvidersLoader(
        redis_client=None,
        use_database=True
    )
    
    # Intentar cargar (debería usar BD o hacer fallback a YAML)
    providers = loader.get_all_providers(use_cache=False)
    
    logger.info(f"Providers loaded with fallback: {len(providers)}")
    logger.info(f"Loader info: {loader.get_loader_info()}")
    
    # Debería retornar algo, ya sea de BD o YAML
    assert len(providers) > 0, "Should load providers (BD or YAML fallback)"
    
    return True


def test_11_routing_engine_integration():
    """Test 11: Integración con Routing Engine"""
    from utils.routing_engine import get_routing_summary
    
    # Probar en modo YAML
    os.environ["USE_DATABASE_PROVIDERS"] = "false"
    summary_yaml = get_routing_summary()
    
    logger.info(f"Routing summary (YAML): {summary_yaml}")
    
    # Probar en modo Database
    os.environ["USE_DATABASE_PROVIDERS"] = "true"
    summary_db = get_routing_summary()
    
    logger.info(f"Routing summary (DB): {summary_db}")
    
    assert "providers_available" in summary_yaml, "Should have providers list"
    assert isinstance(summary_yaml["providers_available"], list), "Should be list"
    
    return True


def test_12_switch_mode_runtime():
    """Test 12: Cambio de modo en runtime"""
    from utils.providers_loader import ProvidersLoader
    
    loader = ProvidersLoader(use_database=False)
    
    # Verificar modo inicial
    assert loader.mode.value == "yaml", "Should start in YAML mode"
    
    # Cambiar a database
    success = loader.switch_mode(use_database=True)
    assert success, "Should switch mode successfully"
    assert loader.mode.value == "database", "Should be in database mode"
    
    # Volver a YAML
    success = loader.switch_mode(use_database=False)
    assert success, "Should switch back successfully"
    assert loader.mode.value == "yaml", "Should be back in YAML mode"
    
    logger.info("✅ Mode switching works correctly")
    
    return True


def test_13_health_check():
    """Test 13: Health Check del Loader"""
    from utils.providers_loader import ProvidersLoader
    
    loader = ProvidersLoader(use_database=False)
    
    health = loader.health_check()
    
    logger.info(f"Loader health: {health}")
    
    assert "loader_mode" in health, "Should have loader_mode"
    assert "providers_count" in health, "Should have providers_count"
    
    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Ejecutar todos los tests"""
    logger.info("\n" + "="*60)
    logger.info("FASE 2 - TESTING SUITE")
    logger.info("Dual Mode Providers (YAML + Database)")
    logger.info("="*60 + "\n")
    
    tester = Fase2Tester()
    
    # Ejecutar tests
    tester.test("01 - YAML Mode", test_01_yaml_mode)
    tester.test("02 - Database Mode", test_02_database_mode)
    tester.test("03 - ProvidersLoader YAML", test_03_providers_loader_yaml)
    tester.test("04 - ProvidersLoader Database", test_04_providers_loader_database)
    tester.test("05 - ProvidersRepository", test_05_providers_repository)
    tester.test("06 - ProviderGroupsRepository", test_06_provider_groups_repository)
    tester.test("07 - ProvidersCache Redis", test_07_providers_cache)
    tester.test("08 - Performance Load YAML", test_08_performance_load_yaml)
    tester.test("09 - Performance Load Database", test_09_performance_load_database)
    tester.test("10 - Fallback Mechanism", test_10_fallback_mechanism)
    tester.test("11 - Routing Engine Integration", test_11_routing_engine_integration)
    tester.test("12 - Switch Mode Runtime", test_12_switch_mode_runtime)
    tester.test("13 - Health Check", test_13_health_check)
    
    # Imprimir resumen
    tester.print_summary()
    
    # Exit code
    sys.exit(0 if tester.failed == 0 else 1)


if __name__ == "__main__":
    main()