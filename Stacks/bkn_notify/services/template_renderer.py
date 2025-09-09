"""
Template rendering service
Renderiza plantillas Jinja2 con variables y manejo de errores
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.utils.template_loader import load_template_files, render_template as render_template_files
from app.utils.config_loader import load_config


async def render_template(
    template_id: str, 
    variables: Dict[str, Any], 
    fallback_content: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    Renderiza template completo con variables
    
    Args:
        template_id: ID del template (ej: "alerta-simple/v1")
        variables: Variables para el template
        fallback_content: Contenido de fallback si el template no existe
    
    Returns:
        Dict con contenido renderizado: {"subject": "...", "body_text": "...", "body_html": "..."}
    """
    
    try:
        # Preparar variables con valores por defecto del sistema
        enriched_variables = await _enrich_template_variables(variables)
        
        # Renderizar template desde filesystem
        rendered_content = render_template_files(template_id, enriched_variables)
        
        # Post-procesar contenido renderizado
        processed_content = await _post_process_rendered_content(rendered_content)
        
        logging.info(f"Template rendered successfully: {template_id}")
        return processed_content
        
    except FileNotFoundError:
        logging.warning(f"Template not found: {template_id}")
        
        if fallback_content:
            # Usar contenido de fallback y renderizar variables
            return await _render_fallback_content(fallback_content, enriched_variables)
        else:
            raise ValueError(f"Template '{template_id}' not found and no fallback provided")
            
    except Exception as e:
        logging.error(f"Template rendering failed for {template_id}: {e}")
        
        if fallback_content:
            logging.info(f"Using fallback content for {template_id}")
            return await _render_fallback_content(fallback_content, enriched_variables)
        else:
            raise


async def render_inline_content(
    subject: Optional[str] = None,
    body_text: Optional[str] = None, 
    body_html: Optional[str] = None,
    variables: Dict[str, Any] = None
) -> Dict[str, str]:
    """
    Renderiza contenido inline (sin template files)
    
    Args:
        subject: Subject template string
        body_text: Body text template string  
        body_html: Body HTML template string
        variables: Variables para renderizar
        
    Returns:
        Dict con contenido renderizado
    """
    
    if not any([subject, body_text, body_html]):
        raise ValueError("At least one content field (subject, body_text, body_html) is required")
    
    try:
        # Preparar variables
        enriched_variables = await _enrich_template_variables(variables or {})
        
        rendered = {}
        
        # Renderizar cada campo si está presente
        if subject:
            rendered["subject"] = await _render_string_template(subject, enriched_variables, "subject")
        
        if body_text:
            rendered["body_text"] = await _render_string_template(body_text, enriched_variables, "body_text")
            
        if body_html:
            rendered["body_html"] = await _render_string_template(body_html, enriched_variables, "body_html")
        
        # Post-procesar
        processed_content = await _post_process_rendered_content(rendered)
        
        logging.info("Inline content rendered successfully")
        return processed_content
        
    except Exception as e:
        logging.error(f"Inline content rendering failed: {e}")
        raise


async def _enrich_template_variables(variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enriquece variables del template con valores del sistema
    """
    
    # Cargar configuración del sistema
    config = load_config()
    
    # Variables base del sistema
    system_variables = {
        # Información del sistema
        "system": {
            "name": config.get("app", {}).get("name", "Notify API"),
            "version": config.get("app", {}).get("version", "1.0.0"),
            "timestamp": datetime.now().isoformat(),
            "year": datetime.now().year
        },
        
        # Información de fecha/hora
        "now": datetime.now(),
        "today": datetime.now().date(),
        "timestamp": datetime.now().isoformat(),
        "timestamp_unix": int(datetime.now().timestamp()),
        
        # Formatos de fecha comunes
        "date_short": datetime.now().strftime("%Y-%m-%d"),
        "date_long": datetime.now().strftime("%B %d, %Y"),
        "time_short": datetime.now().strftime("%H:%M"),
        "time_long": datetime.now().strftime("%H:%M:%S"),
        "datetime_readable": datetime.now().strftime("%B %d, %Y at %H:%M"),
        
        # URLs y enlaces (si están configurados)
        "urls": config.get("urls", {
            "unsubscribe": "#",
            "support": "#",
            "website": "#"
        })
    }
    
    # Combinar variables del usuario con las del sistema
    # Las variables del usuario tienen prioridad
    enriched = {**system_variables, **variables}
    
    # Validar y sanitizar variables críticas
    enriched = await _sanitize_template_variables(enriched)
    
    return enriched


async def _sanitize_template_variables(variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitiza variables para prevenir inyección y errores
    """
    
    sanitized = {}
    
    for key, value in variables.items():
        try:
            # Convertir tipos no serializables
            if isinstance(value, datetime):
                sanitized[key] = value.isoformat()
            elif hasattr(value, 'date'):  # datetime.date
                sanitized[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                # Mantener estructuras complejas como están
                sanitized[key] = value
            else:
                # Convertir a string y sanitizar
                str_value = str(value) if value is not None else ""
                # Remover caracteres de control problemáticos
                sanitized[key] = str_value.replace('\x00', '').replace('\r', '\n')
                
        except Exception as e:
            logging.warning(f"Error sanitizing variable '{key}': {e}")
            # En caso de error, usar string vacío como fallback
            sanitized[key] = ""
    
    return sanitized


async def _render_string_template(template_string: str, variables: Dict[str, Any], field_name: str) -> str:
    """
    Renderiza un string template individual
    """
    
    try:
        from app.utils.template_loader import compile_template
        
        # Compilar y renderizar template string
        compiled_template = compile_template(template_string, f"inline_{field_name}")
        rendered = compiled_template.render(**variables)
        
        return rendered.strip() if field_name == "subject" else rendered
        
    except Exception as e:
        logging.error(f"Error rendering {field_name} template: {e}")
        # Retornar template original como fallback
        return template_string


async def _render_fallback_content(fallback_content: Dict[str, str], variables: Dict[str, Any]) -> Dict[str, str]:
    """
    Renderiza contenido de fallback con variables
    """
    
    rendered = {}
    
    for field, content in fallback_content.items():
        if content:
            try:
                rendered[field] = await _render_string_template(content, variables, field)
            except Exception as e:
                logging.error(f"Error rendering fallback {field}: {e}")
                rendered[field] = content  # Usar sin renderizar como último recurso
    
    return rendered


async def _post_process_rendered_content(content: Dict[str, str]) -> Dict[str, str]:
    """
    Post-procesa contenido renderizado (limpieza, validaciones)
    """
    
    processed = {}
    
    for field, value in content.items():
        if not value:
            continue
            
        try:
            # Limpiar espacios en blanco excesivos
            cleaned = value.strip()
            
            # Normalizar line breaks
            cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
            
            # Para subject, asegurar línea única
            if field == "subject":
                cleaned = cleaned.replace('\n', ' ').replace('\t', ' ')
                # Remover espacios múltiples
                import re
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                
                # Validar longitud del subject
                if len(cleaned) > 998:  # RFC 2822 limit
                    logging.warning(f"Subject too long ({len(cleaned)} chars), truncating")
                    cleaned = cleaned[:995] + "..."
            
            # Para HTML, validación básica
            elif field == "body_html":
                cleaned = await _validate_html_content(cleaned)
            
            processed[field] = cleaned
            
        except Exception as e:
            logging.error(f"Error post-processing {field}: {e}")
            processed[field] = value  # Usar valor original
    
    return processed


async def _validate_html_content(html_content: str) -> str:
    """
    Validación básica de contenido HTML
    """
    
    try:
        # Verificar que no hay scripts maliciosos (básico)
        import re
        
        # Remover comentarios HTML problemáticos
        html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
        
        # Verificar tags problemáticos (básico - no reemplaza un sanitizer real)
        dangerous_tags = ['<script', '<iframe', '<object', '<embed', '<form']
        for tag in dangerous_tags:
            if tag in html_content.lower():
                logging.warning(f"Potentially dangerous HTML tag found: {tag}")
        
        return html_content
        
    except Exception as e:
        logging.error(f"HTML validation error: {e}")
        return html_content


def validate_template_variables(template_id: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida variables contra template sin renderizar
    Útil para debugging y validación previa
    """
    
    try:
        # Cargar template files
        template_files = load_template_files(template_id)
        
        validation_result = {
            "template_id": template_id,
            "variables_provided": list(variables.keys()),
            "validation_passed": True,
            "issues": []
        }
        
        # Intentar compilar templates para detectar variables faltantes
        from jinja2 import meta
        from app.utils.template_loader import get_jinja_environment
        
        env = get_jinja_environment()
        
        for file_type, content in template_files.items():
            try:
                ast = env.parse(content)
                required_vars = meta.find_undeclared_variables(ast)
                
                missing_vars = required_vars - set(variables.keys())
                if missing_vars:
                    validation_result["validation_passed"] = False
                    validation_result["issues"].append({
                        "file": file_type,
                        "type": "missing_variables",
                        "variables": list(missing_vars)
                    })
                    
            except Exception as e:
                validation_result["validation_passed"] = False
                validation_result["issues"].append({
                    "file": file_type,
                    "type": "template_error",
                    "error": str(e)
                })
        
        return validation_result
        
    except Exception as e:
        return {
            "template_id": template_id,
            "validation_passed": False,
            "error": str(e)
        }


def get_template_preview(template_id: str, sample_variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Genera preview de template con variables de ejemplo
    """
    
    sample_vars = sample_variables or {
        "user_name": "John Doe",
        "user_email": "john.doe@example.com",
        "company": "Example Corp",
        "title": "Sample Title",
        "message": "This is a sample message for preview purposes.",
        "amount": 100.00,
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    try:
        rendered = render_template_files(template_id, sample_vars)
        
        return {
            "template_id": template_id,
            "sample_variables": sample_vars,
            "preview": rendered,
            "preview_generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "template_id": template_id,
            "error": str(e),
            "preview_generated_at": datetime.now().isoformat()
        }