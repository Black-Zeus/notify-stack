"""
Template loader utility - CORREGIDO
Carga y maneja plantillas Jinja2 desde filesystem
"""

import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound, TemplateSyntaxError, StrictUndefined

from constants import TEMPLATES_DIR

# Cache global de templates compilados
_template_cache: Dict[str, Template] = {}
_jinja_env: Optional[Environment] = None


def get_jinja_environment() -> Environment:
    """
    Obtiene entorno Jinja2 singleton con configuración segura
    """
    global _jinja_env
    
    if _jinja_env is None:
        try:
            # Verificar que existe directorio de templates
            if not os.path.exists(TEMPLATES_DIR):
                logging.warning(f"Templates directory not found: {TEMPLATES_DIR}")
                os.makedirs(TEMPLATES_DIR, exist_ok=True)
            
            _jinja_env = Environment(
                loader=FileSystemLoader(TEMPLATES_DIR),
                autoescape=True,  # Seguridad: escapar HTML por defecto
                trim_blocks=True,
                lstrip_blocks=True,
                undefined=StrictUndefined  # Fallar si variable no está definida
            )
            
            # Agregar filtros personalizados
            _jinja_env.filters['email_safe'] = email_safe_filter
            _jinja_env.filters['truncate_smart'] = truncate_smart_filter
            
            logging.info("Jinja2 environment initialized")
            
        except Exception as e:
            logging.error(f"Failed to initialize Jinja2 environment: {e}")
            raise
    
    return _jinja_env


def email_safe_filter(text: str) -> str:
    """
    Filtro para hacer texto seguro para email
    """
    if not text:
        return ""
    
    # Remover caracteres problemáticos para email
    safe_text = str(text).replace('\x00', '').replace('\r', '\n')
    return safe_text


def truncate_smart_filter(text: str, length: int = 100, suffix: str = "...") -> str:
    """
    Filtro para truncar texto de forma inteligente
    """
    if not text or len(text) <= length:
        return text
    
    # Truncar en palabra completa si es posible
    truncated = text[:length]
    last_space = truncated.rfind(' ')
    
    if last_space > length * 0.8:  # Si el espacio está cerca del final
        truncated = truncated[:last_space]
    
    return truncated + suffix


def get_template_path(template_id: str) -> str:
    """
    ✅ FUNCIÓN AGREGADA: Convierte template_id a ruta del directorio
    
    Args:
        template_id: ID en formato "template-name/version" o "template-name.version"
    
    Returns:
        Ruta completa al directorio del template
    """
    try:
        # Normalizar template_id: convertir puntos a barras
        if '.' in template_id and '/' not in template_id:
            # Formato: "alerta-simple.v1" -> "alerta-simple/v1"
            template_id = template_id.replace('.', '/', 1)
        
        # Construir ruta completa
        template_path = os.path.join(TEMPLATES_DIR, template_id)
        
        # Verificar que existe
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template directory not found: {template_path}")
        
        if not os.path.isdir(template_path):
            raise ValueError(f"Template path is not a directory: {template_path}")
        
        logging.debug(f"Template path resolved: {template_id} -> {template_path}")
        return template_path
        
    except Exception as e:
        logging.error(f"Error resolving template path for {template_id}: {e}")
        raise


def get_available_templates() -> List[Dict[str, Any]]:
    """
    Lista todos los templates disponibles en el filesystem
    """
    templates = []
    
    try:
        if not os.path.exists(TEMPLATES_DIR):
            logging.warning(f"Templates directory not found: {TEMPLATES_DIR}")
            return []
        
        # Recorrer estructura: templates/{template_name}/{version}/
        for template_name in os.listdir(TEMPLATES_DIR):
            template_path = os.path.join(TEMPLATES_DIR, template_name)
            
            if not os.path.isdir(template_path):
                continue
            
            # Buscar versiones
            for version in os.listdir(template_path):
                version_path = os.path.join(template_path, version)
                
                if not os.path.isdir(version_path):
                    continue
                
                # Verificar archivos disponibles
                available_files = {}
                for file_name in ['subject.txt', 'body.txt', 'body.html']:
                    file_path = os.path.join(version_path, file_name)
                    if os.path.exists(file_path):
                        available_files[file_name.replace('.txt', '').replace('.html', '_html')] = True
                
                if available_files:  # Solo incluir si tiene al menos un archivo
                    template_id = f"{template_name}/{version}"
                    templates.append({
                        "template_id": template_id,
                        "name": template_name,
                        "version": version,
                        "files": available_files,
                        "path": version_path,
                        "has_subject": "subject" in available_files,
                        "has_text": "body" in available_files,
                        "has_html": "body_html" in available_files
                    })
        
        logging.debug(f"Found {len(templates)} available templates")
        return sorted(templates, key=lambda x: x["template_id"])
        
    except Exception as e:
        logging.error(f"Error listing templates: {e}")
        return []


def load_template_files(template_id: str) -> Dict[str, str]:
    """
    ✅ CORREGIDO: Carga archivos de un template específico usando get_template_path
    
    Args:
        template_id: ID del template (ej: "alerta-simple/v1" o "alerta-simple.v1")
    
    Returns:
        Dict con contenido de archivos: {"subject": "...", "body_text": "...", "body_html": "..."}
    """
    
    try:
        # ✅ USAR: get_template_path para resolver la ruta
        template_path = get_template_path(template_id)
        
        template_files = {}
        
        # Cargar subject.txt
        subject_file = os.path.join(template_path, "subject.txt")
        if os.path.exists(subject_file):
            with open(subject_file, 'r', encoding='utf-8') as f:
                template_files["subject"] = f.read().strip()
        
        # Cargar body.txt
        body_file = os.path.join(template_path, "body.txt")
        if os.path.exists(body_file):
            with open(body_file, 'r', encoding='utf-8') as f:
                template_files["body_text"] = f.read()
        
        # Cargar body.html (opcional)
        html_file = os.path.join(template_path, "body.html")
        if os.path.exists(html_file):
            with open(html_file, 'r', encoding='utf-8') as f:
                template_files["body_html"] = f.read()
        
        if not template_files:
            raise ValueError(f"No template files found in: {template_id}")
        
        logging.debug(f"Loaded template files for {template_id}: {list(template_files.keys())}")
        return template_files
        
    except Exception as e:
        logging.error(f"Error loading template {template_id}: {e}")
        raise


def compile_template(template_content: str, template_name: str) -> Template:
    """
    Compila template Jinja2 con cache
    """
    
    cache_key = f"{template_name}:{hash(template_content)}"
    
    if cache_key in _template_cache:
        return _template_cache[cache_key]
    
    try:
        env = get_jinja_environment()
        compiled_template = env.from_string(template_content)
        
        # Cache template compilado
        _template_cache[cache_key] = compiled_template
        
        logging.debug(f"Template compiled and cached: {template_name}")
        return compiled_template
        
    except TemplateSyntaxError as e:
        logging.error(f"Template syntax error in {template_name}: {e}")
        raise ValueError(f"Template syntax error: {e}")
    except Exception as e:
        logging.error(f"Error compiling template {template_name}: {e}")
        raise


def render_template(template_id: str, variables: Dict[str, Any]) -> Dict[str, str]:
    """
    ✅ CORREGIDO: Renderiza template completo con variables
    
    Args:
        template_id: ID del template (ej: "alerta-simple/v1" o "alerta-simple.v1")
        variables: Dict con variables para el template
    
    Returns:
        Dict con contenido renderizado: {"subject": "...", "body_text": "...", "body_html": "..."}
    """
    
    try:
        # Cargar archivos del template
        template_files = load_template_files(template_id)
        
        rendered = {}
        
        # Renderizar cada archivo
        for file_type, content in template_files.items():
            try:
                compiled_template = compile_template(content, f"{template_id}:{file_type}")
                rendered_content = compiled_template.render(**variables)
                rendered[file_type] = rendered_content
                
            except Exception as e:
                logging.error(f"Error rendering {file_type} for template {template_id}: {e}")
                # Continuar con otros archivos en caso de error
                rendered[file_type] = f"Error rendering template: {str(e)}"
        
        logging.info(f"Template rendered successfully: {template_id}")
        return rendered
        
    except Exception as e:
        logging.error(f"Error rendering template {template_id}: {e}")
        raise


def validate_template_syntax(template_id: str) -> Dict[str, Any]:
    """
    Valida sintaxis de un template sin renderizar
    
    Returns:
        Dict con resultado de validación para cada archivo
    """
    
    try:
        template_files = load_template_files(template_id)
        validation_results = {}
        
        for file_type, content in template_files.items():
            try:
                compile_template(content, f"{template_id}:{file_type}")
                validation_results[file_type] = {
                    "valid": True,
                    "error": None
                }
            except Exception as e:
                validation_results[file_type] = {
                    "valid": False,
                    "error": str(e)
                }
        
        return validation_results
        
    except Exception as e:
        logging.error(f"Error validating template {template_id}: {e}")
        raise


def clear_template_cache():
    """
    Limpia cache de templates compilados
    """
    global _template_cache
    _template_cache.clear()
    logging.info("Template cache cleared")


def get_template_variables(template_id: str) -> List[str]:
    """
    ✅ BONUS: Extrae variables utilizadas en un template
    
    Returns:
        Lista de nombres de variables encontradas en el template
    """
    
    try:
        template_files = load_template_files(template_id)
        variables_found = set()
        
        # Usar regex simple para encontrar variables {{ variable }}
        import re
        variable_pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
        
        for file_type, content in template_files.items():
            matches = re.findall(variable_pattern, content)
            variables_found.update(matches)
        
        return sorted(list(variables_found))
        
    except Exception as e:
        logging.error(f"Error extracting variables from template {template_id}: {e}")
        return []