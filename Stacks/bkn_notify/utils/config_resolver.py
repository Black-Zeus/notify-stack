"""
Config Resolver - Variable Substitution Module
Procesa plantillas ${VARIABLE} en configuraciones YAML
"""

import os
import re
import logging
from typing import Dict, Any, Union, List


class ConfigResolver:
    """
    Resuelve variables de entorno en configuraciones YAML/JSON
    """
    
    # Patrón para detectar plantillas ${VARIABLE}
    TEMPLATE_PATTERN = re.compile(r'\$\{([^}]+)\}')
    
    def __init__(self, warn_missing: bool = True, strict_mode: bool = False):
        """
        Inicializa el resolver
        
        Args:
            warn_missing: Advertir sobre variables no encontradas
            strict_mode: Fallar si variable no existe (True) o usar string vacío (False)
        """
        self.warn_missing = warn_missing
        self.strict_mode = strict_mode
        self._missing_vars = set()
    
    def substitute_env_vars(self, config: Union[Dict, List, str, Any]) -> Any:
        """
        Sustituye variables de entorno recursivamente en cualquier estructura
        
        Args:
            config: Configuración a procesar (dict, list, str, etc.)
            
        Returns:
            Configuración con variables sustituidas
        """
        if isinstance(config, dict):
            return {key: self.substitute_env_vars(value) for key, value in config.items()}
        
        elif isinstance(config, list):
            return [self.substitute_env_vars(item) for item in config]
        
        elif isinstance(config, str):
            return self._resolve_string_template(config)
        
        else:
            # Tipos primitivos (int, bool, None, etc.) sin cambios
            return config
    
    def _resolve_string_template(self, template: str) -> str:
        """
        Resuelve plantillas en un string individual
        
        Args:
            template: String que puede contener ${VARIABLE}
            
        Returns:
            String con variables sustituidas
        """
        def replace_var(match):
            var_name = match.group(1)
            var_value = os.getenv(var_name)
            
            if var_value is not None:
                return var_value
            
            # Variable no encontrada
            if var_name not in self._missing_vars:
                self._missing_vars.add(var_name)
                
                if self.warn_missing:
                    logging.warning(f"Environment variable '{var_name}' not found")
            
            if self.strict_mode:
                raise ValueError(f"Required environment variable '{var_name}' not set")
            
            # Modo permisivo: devolver string vacío
            return ""
        
        return self.TEMPLATE_PATTERN.sub(replace_var, template)
    
    def validate_required_vars(self, config: Dict[str, Any], required_vars: List[str]) -> List[str]:
        """
        Valida que variables críticas estén definidas
        
        Args:
            config: Configuración procesada
            required_vars: Lista de variables que deben existir
            
        Returns:
            Lista de variables faltantes
        """
        missing = []
        
        for var_name in required_vars:
            if not os.getenv(var_name):
                missing.append(var_name)
        
        if missing and self.warn_missing:
            logging.error(f"Critical environment variables missing: {missing}")
        
        return missing
    
    def get_missing_vars(self) -> set:
        """
        Retorna variables que no se encontraron durante la substitución
        """
        return self._missing_vars.copy()
    
    def clear_missing_vars(self):
        """
        Limpia el registro de variables faltantes
        """
        self._missing_vars.clear()


# Factory functions para uso directo
def substitute_config_vars(config: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
    """
    Función de conveniencia para sustituir variables en configuración
    
    Args:
        config: Configuración a procesar
        strict: Fallar si variable no existe
        
    Returns:
        Configuración con variables sustituidas
    """
    resolver = ConfigResolver(strict_mode=strict)
    return resolver.substitute_env_vars(config)


def validate_twilio_vars() -> List[str]:
    """
    Valida variables críticas de Twilio
    
    Returns:
        Lista de variables faltantes
    """
    required = [
        'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN'
    ]
    
    missing = []
    for var in required:
        if not os.getenv(var):
            missing.append(var)
    
    return missing


def validate_smtp_vars(provider_prefix: str) -> List[str]:
    """
    Valida variables SMTP para un proveedor específico
    
    Args:
        provider_prefix: Prefijo del proveedor (ej: "SMTP_GMAIL")
        
    Returns:
        Lista de variables faltantes
    """
    required = [
        f'{provider_prefix}_HOST',
        f'{provider_prefix}_PORT',
        f'{provider_prefix}_USERNAME',
        f'{provider_prefix}_PASSWORD'
    ]
    
    missing = []
    for var in required:
        if not os.getenv(var):
            missing.append(var)
    
    return missing


def debug_config_vars(config: Dict[str, Any], prefix: str = "") -> None:
    """
    Debug: imprime todas las plantillas encontradas en configuración
    
    Args:
        config: Configuración a analizar
        prefix: Prefijo para logging (recursión)
    """
    pattern = re.compile(r'\$\{([^}]+)\}')
    
    def find_templates(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                find_templates(value, f"{path}.{key}" if path else key)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                find_templates(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            matches = pattern.findall(obj)
            if matches:
                for var_name in matches:
                    var_value = os.getenv(var_name)
                    status = "✓" if var_value else "✗"
                    logging.info(f"{status} {path}: ${{{var_name}}} = {var_value or 'MISSING'}")
    
    logging.info(f"--- Config Variables Debug{' (' + prefix + ')' if prefix else ''} ---")
    find_templates(config)


# Ejemplo de uso y testing
if __name__ == "__main__":
    # Configuración de ejemplo con plantillas
    test_config = {
        "providers": {
            "twilio": {
                "account_sid": "${TWILIO_ACCOUNT_SID}",
                "auth_token": "${TWILIO_AUTH_TOKEN}",
                "from_number": "${TWILIO_FROM_NUMBER}",
                "endpoints": [
                    "https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Messages.json"
                ]
            },
            "smtp": {
                "host": "${SMTP_HOST}",
                "credentials": {
                    "username": "${SMTP_USER}",
                    "password": "${SMTP_PASS}"
                }
            }
        }
    }
    
    # Resolver configuración
    resolver = ConfigResolver()
    resolved = resolver.substitute_env_vars(test_config)
    
    print("=== Original Config ===")
    print(test_config)
    print("\n=== Resolved Config ===")
    print(resolved)
    print(f"\n=== Missing Variables ===")
    print(resolver.get_missing_vars())