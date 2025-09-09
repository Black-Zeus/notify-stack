"""
Email validation service
Validación completa de direcciones de email y contenido
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from email_validator import validate_email as validate_email_lib, EmailNotValidError
import dns.resolver
import socket

from utils.config_loader import load_policy_config


class EmailValidator:
    """
    Validador completo de emails con verificaciones múltiples
    """
    
    def __init__(self):
        self.policy = load_policy_config()
        self.dns_cache = {}  # Cache simple para verificaciones DNS
    
    async def validate_email_address(
        self, 
        email: str, 
        check_deliverability: bool = True,
        check_mx: bool = False
    ) -> Dict[str, Any]:
        """
        Valida dirección de email completa
        
        Args:
            email: Dirección de email a validar
            check_deliverability: Verificar si el email es deliverable
            check_mx: Verificar registros MX del dominio
            
        Returns:
            Dict con resultado de validación detallado
        """
        
        validation_result = {
            "email": email,
            "is_valid": False,
            "normalized": None,
            "local_part": None,
            "domain": None,
            "checks": {
                "format": False,
                "deliverable": False,
                "mx_exists": False,
                "domain_exists": False,
                "disposable": False,
                "role_based": False
            },
            "warnings": [],
            "errors": []
        }
        
        try:
            # 1. Validación de formato básico
            format_result = await self._validate_format(email)
            validation_result["checks"]["format"] = format_result["valid"]
            
            if not format_result["valid"]:
                validation_result["errors"].extend(format_result["errors"])
                return validation_result
            
            validation_result["normalized"] = format_result["normalized"]
            validation_result["local_part"] = format_result["local_part"]
            validation_result["domain"] = format_result["domain"]
            
            # 2. Verificación de deliverability si está habilitada
            if check_deliverability:
                deliverable_result = await self._check_deliverability(format_result["normalized"])
                validation_result["checks"]["deliverable"] = deliverable_result["deliverable"]
                if deliverable_result.get("warnings"):
                    validation_result["warnings"].extend(deliverable_result["warnings"])
            
            # 3. Verificación MX si está habilitada
            if check_mx:
                mx_result = await self._check_mx_records(format_result["domain"])
                validation_result["checks"]["mx_exists"] = mx_result["has_mx"]
                validation_result["checks"]["domain_exists"] = mx_result["domain_exists"]
                if mx_result.get("warnings"):
                    validation_result["warnings"].extend(mx_result["warnings"])
            
            # 4. Verificación de dominio desechable
            disposable_result = await self._check_disposable_domain(format_result["domain"])
            validation_result["checks"]["disposable"] = disposable_result["is_disposable"]
            if disposable_result["is_disposable"]:
                validation_result["warnings"].append("Email uses disposable domain")
            
            # 5. Verificación de email basado en rol
            role_result = await self._check_role_based(format_result["local_part"])
            validation_result["checks"]["role_based"] = role_result["is_role"]
            if role_result["is_role"]:
                validation_result["warnings"].append(f"Role-based email detected: {role_result['role']}")
            
            # Determinar validez general
            validation_result["is_valid"] = (
                validation_result["checks"]["format"] and
                (not check_deliverability or validation_result["checks"]["deliverable"]) and
                (not check_mx or validation_result["checks"]["mx_exists"])
            )
            
            return validation_result
            
        except Exception as e:
            logging.error(f"Email validation failed for {email}: {e}")
            validation_result["errors"].append(f"Validation error: {str(e)}")
            return validation_result
    
    async def _validate_format(self, email: str) -> Dict[str, Any]:
        """
        Validación de formato usando email-validator library
        """
        try:
            # Usar librería email-validator para validación RFC compliant
            validated = validate_email_lib(email)
            
            return {
                "valid": True,
                "normalized": validated.email,
                "local_part": validated.local,
                "domain": validated.domain,
                "errors": []
            }
            
        except EmailNotValidError as e:
            return {
                "valid": False,
                "normalized": None,
                "local_part": None,
                "domain": None,
                "errors": [str(e)]
            }
    
    async def _check_deliverability(self, email: str) -> Dict[str, Any]:
        """
        Verificación básica de deliverability
        """
        try:
            # Usar email-validator con verificación de deliverability
            validated = validate_email_lib(email, check_deliverability=True)
            
            return {
                "deliverable": True,
                "warnings": []
            }
            
        except EmailNotValidError as e:
            return {
                "deliverable": False,
                "warnings": [f"Deliverability check failed: {str(e)}"]
            }
    
    async def _check_mx_records(self, domain: str) -> Dict[str, Any]:
        """
        Verificación de registros MX del dominio
        """
        # Verificar cache
        if domain in self.dns_cache:
            return self.dns_cache[domain]
        
        result = {
            "has_mx": False,
            "domain_exists": False,
            "mx_records": [],
            "warnings": []
        }
        
        try:
            # Verificar registros MX
            mx_records = dns.resolver.resolve(domain, 'MX')
            result["has_mx"] = len(mx_records) > 0
            result["domain_exists"] = True
            result["mx_records"] = [str(mx) for mx in mx_records]
            
        except dns.resolver.NXDOMAIN:
            result["warnings"].append(f"Domain {domain} does not exist")
        except dns.resolver.NoAnswer:
            # Dominio existe pero sin MX - verificar registro A
            try:
                dns.resolver.resolve(domain, 'A')
                result["domain_exists"] = True
                result["warnings"].append(f"Domain {domain} has no MX records but has A record")
            except:
                result["warnings"].append(f"Domain {domain} has no MX or A records")
        except Exception as e:
            result["warnings"].append(f"DNS lookup failed for {domain}: {str(e)}")
        
        # Cache resultado por 5 minutos
        self.dns_cache[domain] = result
        
        return result
    
    async def _check_disposable_domain(self, domain: str) -> Dict[str, Any]:
        """
        Verificación de dominios desechables/temporales
        """
        # Lista básica de dominios desechables conocidos
        disposable_domains = {
            '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
            'mailinator.com', 'throwaway.email', '10minutemail.net',
            'temp-mail.org', 'getairmail.com', 'yopmail.com',
            'sharklasers.com', 'guerrillamailblock.com', 'pokemail.net',
            'spam4.me', 'bccto.me', 'chacuo.net', 'dispostable.com'
        }
        
        # Verificar si el dominio está en la lista
        is_disposable = domain.lower() in disposable_domains
        
        # Verificar patrones comunes de dominios temporales
        disposable_patterns = [
            r'.*temp.*mail.*',
            r'.*disposable.*',
            r'.*throw.*away.*',
            r'.*guerrilla.*',
            r'.*minute.*mail.*'
        ]
        
        if not is_disposable:
            for pattern in disposable_patterns:
                if re.match(pattern, domain.lower()):
                    is_disposable = True
                    break
        
        return {
            "is_disposable": is_disposable,
            "domain": domain
        }
    
    async def _check_role_based(self, local_part: str) -> Dict[str, Any]:
        """
        Verificación de emails basados en rol
        """
        role_based_locals = {
            'admin', 'administrator', 'postmaster', 'hostmaster', 'webmaster',
            'www', 'ftp', 'mail', 'email', 'marketing', 'sales', 'support',
            'help', 'info', 'contact', 'service', 'noreply', 'no-reply',
            'donotreply', 'do-not-reply', 'abuse', 'security', 'privacy',
            'legal', 'billing', 'accounts', 'newsletter', 'notifications'
        }
        
        local_lower = local_part.lower()
        
        # Verificación exacta
        if local_lower in role_based_locals:
            return {
                "is_role": True,
                "role": local_lower
            }
        
        # Verificación de patrones
        role_patterns = [
            r'.*admin.*',
            r'.*support.*',
            r'.*no.*reply.*',
            r'.*contact.*',
            r'.*info.*'
        ]
        
        for pattern in role_patterns:
            if re.match(pattern, local_lower):
                return {
                    "is_role": True,
                    "role": "pattern_match"
                }
        
        return {
            "is_role": False,
            "role": None
        }
    
    async def validate_email_list(
        self, 
        emails: List[str],
        max_errors: int = 10,
        check_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Valida lista de emails con optimizaciones
        """
        results = {
            "total_emails": len(emails),
            "valid_emails": [],
            "invalid_emails": [],
            "warnings": [],
            "duplicates": [],
            "summary": {
                "valid_count": 0,
                "invalid_count": 0,
                "warning_count": 0,
                "duplicate_count": 0
            }
        }
        
        seen_emails = set()
        error_count = 0
        
        for email in emails:
            # Verificar duplicados
            email_normalized = email.strip().lower()
            if check_duplicates and email_normalized in seen_emails:
                results["duplicates"].append(email)
                results["summary"]["duplicate_count"] += 1
                continue
            seen_emails.add(email_normalized)
            
            # Validar email
            validation = await self.validate_email_address(email, check_deliverability=False)
            
            if validation["is_valid"]:
                results["valid_emails"].append({
                    "email": email,
                    "normalized": validation["normalized"],
                    "warnings": validation["warnings"]
                })
                results["summary"]["valid_count"] += 1
                
                if validation["warnings"]:
                    results["summary"]["warning_count"] += 1
            else:
                results["invalid_emails"].append({
                    "email": email,
                    "errors": validation["errors"]
                })
                results["summary"]["invalid_count"] += 1
                error_count += 1
                
                # Parar si hay demasiados errores
                if error_count >= max_errors:
                    results["warnings"].append(f"Stopped validation after {max_errors} errors")
                    break
        
        return results
    
    async def validate_content(
        self,
        subject: str,
        body_text: str = None,
        body_html: str = None
    ) -> Dict[str, Any]:
        """
        Valida contenido del email (subject y body)
        """
        validation = {
            "subject": {"valid": True, "warnings": [], "errors": []},
            "body_text": {"valid": True, "warnings": [], "errors": []},
            "body_html": {"valid": True, "warnings": [], "errors": []},
            "overall_valid": True
        }
        
        # Validar subject
        if not subject or not subject.strip():
            validation["subject"]["valid"] = False
            validation["subject"]["errors"].append("Subject is required")
        elif len(subject) > 998:  # RFC 2822 limit
            validation["subject"]["valid"] = False
            validation["subject"]["errors"].append("Subject exceeds 998 characters")
        elif len(subject) > 78:  # Recommended limit
            validation["subject"]["warnings"].append("Subject longer than 78 characters")
        
        # Verificar caracteres problemáticos en subject
        if re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', subject):
            validation["subject"]["warnings"].append("Subject contains control characters")
        
        # Validar body_text
        if body_text:
            if len(body_text) > 1048576:  # 1MB limit
                validation["body_text"]["valid"] = False
                validation["body_text"]["errors"].append("Text body exceeds 1MB limit")
        
        # Validar body_html
        if body_html:
            if len(body_html) > 1048576:  # 1MB limit
                validation["body_html"]["valid"] = False
                validation["body_html"]["errors"].append("HTML body exceeds 1MB limit")
            
            # Verificar tags peligrosos básicos
            dangerous_tags = ['<script', '<iframe', '<object', '<embed']
            for tag in dangerous_tags:
                if tag in body_html.lower():
                    validation["body_html"]["warnings"].append(f"Potentially dangerous tag found: {tag}")
        
        # Validación general
        validation["overall_valid"] = (
            validation["subject"]["valid"] and
            validation["body_text"]["valid"] and
            validation["body_html"]["valid"]
        )
        
        return validation
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del validador
        """
        return {
            "dns_cache_size": len(self.dns_cache),
            "features": {
                "format_validation": True,
                "deliverability_check": True,
                "mx_record_check": True,
                "disposable_domain_check": True,
                "role_based_check": True,
                "content_validation": True,
                "bulk_validation": True
            },
            "limits": {
                "subject_max_length": 998,
                "body_max_size": 1048576,
                "bulk_validation_max_errors": 10
            }
        }
    
    def clear_cache(self):
        """
        Limpia cache DNS
        """
        self.dns_cache.clear()
        logging.info("Email validator DNS cache cleared")