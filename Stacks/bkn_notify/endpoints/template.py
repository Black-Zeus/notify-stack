"""
Template endpoints - Consulta de templates disponibles y sus variables
"""

import os
import yaml
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

from constants import HTTP_404_NOT_FOUND, TEMPLATES_DIR
from models.template_info import TemplateInfo, TemplateListResponse, TemplateDetailResponse

router = APIRouter()


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(None, description="Filtrar por categoría"),
    search: Optional[str] = Query(None, description="Buscar en nombre o descripción")
):
    """
    Lista todos los templates disponibles en el sistema
    
    - Escanea el directorio de templates
    - Lee metadata de variables.yml
    - Permite filtrado por categoría y búsqueda
    - Muestra versiones disponibles
    """
    
    try:
        templates = []
        templates_found = 0
        
        # Escanear directorio de templates
        if not os.path.exists(TEMPLATES_DIR):
            logging.warning(f"Templates directory not found: {TEMPLATES_DIR}")
            return TemplateListResponse(
                templates=[],
                total_count=0,
                categories=[],
                retrieved_at=datetime.utcnow().isoformat()
            )
        
        categories_found = set()
        
        # Iterar por cada template
        for template_name in os.listdir(TEMPLATES_DIR):
            template_path = os.path.join(TEMPLATES_DIR, template_name)
            
            if not os.path.isdir(template_path):
                continue
                
            # Buscar versiones del template
            versions = []
            for version in os.listdir(template_path):
                version_path = os.path.join(template_path, version)
                
                if not os.path.isdir(version_path):
                    continue
                    
                # Verificar que tenga los archivos requeridos
                required_files = ['subject.txt', 'body.txt', 'body.html', 'variables.yml']
                has_all_files = all(
                    os.path.exists(os.path.join(version_path, f)) 
                    for f in required_files
                )
                
                if has_all_files:
                    versions.append(version)
            
            if not versions:
                continue
                
            # Leer información del template desde la versión más reciente
            latest_version = sorted(versions)[-1]
            template_id = f"{template_name}.{latest_version}"  # Usar punto en lugar de slash
            
            try:
                template_info = await _get_template_info(template_name, latest_version)
                
                # Aplicar filtros
                if category and template_info.get('category', '').lower() != category.lower():
                    continue
                    
                if search:
                    search_text = search.lower()
                    name_match = search_text in template_info.get('name', '').lower()
                    desc_match = search_text in template_info.get('description', '').lower()
                    if not (name_match or desc_match):
                        continue
                
                # Agregar información del template
                template_data = TemplateInfo(
                    template_id=template_id,
                    name=template_info.get('name', template_name.replace('-', ' ').title()),
                    description=template_info.get('description', 'No description available'),
                    category=template_info.get('category', 'general'),
                    versions=versions,
                    latest_version=latest_version,
                    required_vars=template_info.get('variables', []),
                    optional_sections=template_info.get('conditionals', []),
                    created_at=_get_template_creation_date(template_name, latest_version)
                )
                
                templates.append(template_data)
                categories_found.add(template_data.category)
                templates_found += 1
                
            except Exception as e:
                logging.warning(f"Failed to load template info for {template_name}/{latest_version}: {e}")
                continue
        
        # Ordenar templates por nombre
        templates.sort(key=lambda t: t.name)
        
        return TemplateListResponse(
            templates=templates,
            total_count=templates_found,
            categories=sorted(list(categories_found)),
            retrieved_at=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logging.error(f"Failed to list templates: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "template_listing_failed",
                "message": "Failed to retrieve template list"
            }
        )


@router.get("/templates/{template_id}/info", response_model=TemplateDetailResponse)
async def get_template_info(template_id: str):
    """
    Obtiene información detallada de un template específico
    
    - Lee variables.yml para metadata completa
    - Muestra variables requeridas y opcionales
    - Incluye ejemplos de uso
    - Estadísticas del template
    """
    
    try:
        # Parsear template_id con formato: template-name.version
        if '.' not in template_id:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail={
                    "error": "invalid_template_id",
                    "message": "Template ID must be in format 'template-name.version'"
                }
            )
        
        # Convertir de formato punto a slash para filesystem
        template_name, version = template_id.split('.', 1)
        
        # Verificar que el template existe
        template_path = os.path.join(TEMPLATES_DIR, template_name, version)
        if not os.path.exists(template_path):
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail={
                    "error": "template_not_found",
                    "message": f"Template '{template_id}' not found"
                }
            )
        
        # Leer información del template
        template_info = await _get_template_info(template_name, version)
        
        # Obtener estadísticas del template
        stats = await _get_template_stats(template_path)
        
        # Leer contenido de archivos para análisis
        files_info = await _analyze_template_files(template_path)
        
        return TemplateDetailResponse(
            template_id=template_id,  # Mantener formato con punto para respuesta
            name=template_info.get('name', template_name.replace('-', ' ').title()),
            description=template_info.get('description', 'No description available'),
            category=template_info.get('category', 'general'),
            version=version,
            required_variables=template_info.get('variables', []),
            conditional_sections=template_info.get('conditionals', []),
            example_usage=template_info.get('example', {}),
            files_info=files_info,
            statistics=stats,
            last_modified=_get_template_last_modified(template_path),
            created_at=_get_template_creation_date(template_name, version)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to get template info for {template_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "template_info_failed",
                "message": f"Failed to retrieve template information for '{template_id}'"
            }
        )


async def _get_template_info(template_name: str, version: str) -> Dict[str, Any]:
    """Lee y parsea el archivo variables.yml del template"""
    
    variables_file = os.path.join(TEMPLATES_DIR, template_name, version, 'variables.yml')
    
    if not os.path.exists(variables_file):
        return {
            'name': template_name.replace('-', ' ').title(),
            'description': 'No variables.yml found',
            'variables': [],
            'conditionals': [],
            'example': {}
        }
    
    try:
        with open(variables_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logging.warning(f"Failed to parse variables.yml for {template_name}/{version}: {e}")
        return {
            'name': template_name.replace('-', ' ').title(),
            'description': f'Error reading variables.yml: {str(e)}',
            'variables': [],
            'conditionals': [],
            'example': {}
        }


async def _analyze_template_files(template_path: str) -> Dict[str, Any]:
    """Analiza los archivos del template para obtener estadísticas"""
    
    files_info = {}
    
    template_files = ['subject.txt', 'body.txt', 'body.html']
    
    for filename in template_files:
        file_path = os.path.join(template_path, filename)
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Contar variables {{ }} y condicionales {% %}
                import re
                variables_found = set(re.findall(r'\{\{\s*([^}|\s]+)(?:\|[^}]*)?\s*\}\}', content))
                conditionals_found = set(re.findall(r'\{\%\s*if\s+([^%\s]+)\s*\%\}', content))
                
                files_info[filename] = {
                    'size_bytes': len(content.encode('utf-8')),
                    'line_count': content.count('\n') + 1,
                    'variables_used': sorted(list(variables_found)),
                    'conditionals_used': sorted(list(conditionals_found)),
                    'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                }
                
            except Exception as e:
                files_info[filename] = {
                    'error': f'Failed to analyze: {str(e)}'
                }
        else:
            files_info[filename] = {
                'status': 'missing'
            }
    
    return files_info


async def _get_template_stats(template_path: str) -> Dict[str, Any]:
    """Obtiene estadísticas del template"""
    
    stats = {
        'total_files': 0,
        'total_size_bytes': 0,
        'has_all_required_files': False
    }
    
    required_files = ['subject.txt', 'body.txt', 'body.html', 'variables.yml']
    existing_files = 0
    
    for filename in required_files:
        file_path = os.path.join(template_path, filename)
        if os.path.exists(file_path):
            existing_files += 1
            stats['total_size_bytes'] += os.path.getsize(file_path)
    
    stats['total_files'] = existing_files
    stats['has_all_required_files'] = existing_files == len(required_files)
    
    return stats


def _get_template_creation_date(template_name: str, version: str) -> str:
    """Obtiene la fecha de creación del template"""
    
    template_path = os.path.join(TEMPLATES_DIR, template_name, version)
    
    try:
        # Usar la fecha de creación del directorio
        creation_time = os.path.getctime(template_path)
        return datetime.fromtimestamp(creation_time).isoformat()
    except:
        return datetime.utcnow().isoformat()


def _get_template_last_modified(template_path: str) -> str:
    """Obtiene la fecha de última modificación del template"""
    
    try:
        # Buscar el archivo más recientemente modificado
        latest_mtime = 0
        
        for root, dirs, files in os.walk(template_path):
            for file in files:
                file_path = os.path.join(root, file)
                mtime = os.path.getmtime(file_path)
                if mtime > latest_mtime:
                    latest_mtime = mtime
        
        return datetime.fromtimestamp(latest_mtime).isoformat()
    except:
        return datetime.utcnow().isoformat()