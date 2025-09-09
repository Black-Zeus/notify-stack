"""
API sender service
Maneja envío de emails via APIs externas (SendGrid, SES, etc.)
"""

import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
import base64

from app.constants import SMTP_TIMEOUT


class APISender:
    """
    Cliente para envío via APIs externas de email
    """
    
    def __init__(self, provider_config: Dict[str, Any]):
        """
        Inicializa API sender con configuración del proveedor
        
        Args:
            provider_config: Dict con endpoint, api_key, provider_type, etc.
        """
        self.config = provider_config
        self.endpoint = provider_config['endpoint']
        self.api_key = provider_config['api_key']
        self.provider_type = provider_config.get('provider_type', 'generic')
        self.timeout = provider_config.get('timeout', SMTP_TIMEOUT)
        
        # Configuración específica por proveedor
        self.from_email = provider_config.get('from_email', '')
        self.from_name = provider_config.get('from_name', '')
        self.reply_to = provider_config.get('reply_to', '')
        
        # Headers personalizados
        self.custom_headers = provider_config.get('headers', {})
    
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body_text: str = None,
        body_html: str = None,
        cc: List[str] = None,
        bcc: List[str] = None,
        attachments: List[Dict[str, Any]] = None,
        message_id: str = None,
        custom_headers: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Envía email via API externa
        
        Returns:
            Dict con resultado del envío
        """
        
        start_time = datetime.now()
        
        try:
            # Validar parámetros
            self._validate_send_params(to, subject, body_text, body_html)
            
            # Construir payload según el proveedor
            if self.provider_type == 'sendgrid':
                payload = await self._build_sendgrid_payload(
                    to, subject, body_text, body_html, cc, bcc, attachments, message_id, custom_headers
                )
                response = await self._send_sendgrid(payload)
            elif self.provider_type == 'ses':
                payload = await self._build_ses_payload(
                    to, subject, body_text, body_html, cc, bcc, attachments, message_id, custom_headers
                )
                response = await self._send_ses(payload)
            elif self.provider_type == 'mailgun':
                payload = await self._build_mailgun_payload(
                    to, subject, body_text, body_html, cc, bcc, attachments, message_id, custom_headers
                )
                response = await self._send_mailgun(payload)
            else:
                # Proveedor genérico
                payload = await self._build_generic_payload(
                    to, subject, body_text, body_html, cc, bcc, attachments, message_id, custom_headers
                )
                response = await self._send_generic(payload)
            
            # Calcular tiempo de envío
            end_time = datetime.now()
            send_duration = (end_time - start_time).total_seconds()
            
            # Procesar respuesta
            if response.get('success', False):
                result = {
                    "success": True,
                    "message_id": message_id,
                    "provider": f"api_{self.provider_type}",
                    "provider_config": self.endpoint,
                    "recipients_count": len(to) + len(cc or []) + len(bcc or []),
                    "send_duration": send_duration,
                    "api_response": response,
                    "sent_at": end_time.isoformat()
                }
                
                logging.info(f"Email sent successfully via {self.provider_type} API")
                return result
            else:
                raise Exception(f"API responded with error: {response.get('error', 'Unknown error')}")
                
        except Exception as e:
            end_time = datetime.now()
            send_duration = (end_time - start_time).total_seconds()
            
            logging.error(f"API send failed ({self.provider_type}): {e}")
            
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "provider": f"api_{self.provider_type}",
                "provider_config": self.endpoint,
                "send_duration": send_duration,
                "failed_at": end_time.isoformat()
            }
    
    def _validate_send_params(
        self, 
        to: List[str], 
        subject: str, 
        body_text: str, 
        body_html: str
    ):
        """
        Valida parámetros de envío
        """
        if not to or len(to) == 0:
            raise ValueError("At least one recipient is required")
        
        if not subject:
            raise ValueError("Subject is required")
        
        if not body_text and not body_html:
            raise ValueError("Either body_text or body_html is required")
        
        if not self.from_email:
            raise ValueError("from_email is required for API sending")
    
    async def _build_sendgrid_payload(
        self, to, subject, body_text, body_html, cc, bcc, attachments, message_id, custom_headers
    ) -> Dict[str, Any]:
        """
        Construye payload para SendGrid API v3
        """
        
        # Convertir lista de emails a formato SendGrid
        to_list = [{"email": email} for email in to]
        
        payload = {
            "from": {
                "email": self.from_email,
                "name": self.from_name
            },
            "personalizations": [{
                "to": to_list,
                "subject": subject
            }],
            "content": []
        }
        
        # Agregar CC/BCC
        if cc:
            payload["personalizations"][0]["cc"] = [{"email": email} for email in cc]
        if bcc:
            payload["personalizations"][0]["bcc"] = [{"email": email} for email in bcc]
        
        # Contenido
        if body_text:
            payload["content"].append({
                "type": "text/plain",
                "value": body_text
            })
        if body_html:
            payload["content"].append({
                "type": "text/html", 
                "value": body_html
            })
        
        # Reply-to
        if self.reply_to:
            payload["reply_to"] = {"email": self.reply_to}
        
        # Headers personalizados
        if custom_headers:
            payload["headers"] = custom_headers
        
        # Attachments
        if attachments:
            payload["attachments"] = []
            for attachment in attachments:
                payload["attachments"].append({
                    "content": attachment["content"],
                    "filename": attachment["filename"],
                    "type": attachment.get("content_type", "application/octet-stream")
                })
        
        return payload
    
    async def _send_sendgrid(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía via SendGrid API
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.endpoint}/v3/mail/send",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 202:
                return {
                    "success": True,
                    "provider_message_id": response.headers.get("X-Message-Id"),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"SendGrid API error: {response.status_code} - {response.text}",
                    "status_code": response.status_code
                }
    
    async def _build_ses_payload(
        self, to, subject, body_text, body_html, cc, bcc, attachments, message_id, custom_headers
    ) -> Dict[str, Any]:
        """
        Construye payload para Amazon SES
        """
        
        payload = {
            "Source": f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email,
            "Destination": {
                "ToAddresses": to
            },
            "Message": {
                "Subject": {
                    "Data": subject,
                    "Charset": "UTF-8"
                },
                "Body": {}
            }
        }
        
        # CC/BCC
        if cc:
            payload["Destination"]["CcAddresses"] = cc
        if bcc:
            payload["Destination"]["BccAddresses"] = bcc
        
        # Contenido
        if body_text:
            payload["Message"]["Body"]["Text"] = {
                "Data": body_text,
                "Charset": "UTF-8"
            }
        if body_html:
            payload["Message"]["Body"]["Html"] = {
                "Data": body_html,
                "Charset": "UTF-8"
            }
        
        # Reply-to
        if self.reply_to:
            payload["ReplyToAddresses"] = [self.reply_to]
        
        return payload
    
    async def _send_ses(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía via Amazon SES API
        """
        # SES requiere AWS signature - implementación simplificada
        headers = {
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": "SimpleEmailService.SendEmail"
        }
        
        # Nota: En implementación real necesitaría AWS signature
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.endpoint,
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "provider_message_id": response.json().get("MessageId"),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"SES API error: {response.status_code} - {response.text}",
                    "status_code": response.status_code
                }
    
    async def _build_mailgun_payload(
        self, to, subject, body_text, body_html, cc, bcc, attachments, message_id, custom_headers
    ) -> Dict[str, Any]:
        """
        Construye payload para Mailgun API
        """
        
        payload = {
            "from": f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email,
            "to": to,
            "subject": subject
        }
        
        # CC/BCC
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        
        # Contenido
        if body_text:
            payload["text"] = body_text
        if body_html:
            payload["html"] = body_html
        
        # Headers personalizados
        if custom_headers:
            for key, value in custom_headers.items():
                payload[f"h:{key}"] = value
        
        return payload
    
    async def _send_mailgun(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía via Mailgun API
        """
        auth = ("api", self.api_key)
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.endpoint}/messages",
                data=payload,
                auth=auth
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "provider_message_id": result.get("id"),
                    "message": result.get("message"),
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"Mailgun API error: {response.status_code} - {response.text}",
                    "status_code": response.status_code
                }
    
    async def _build_generic_payload(
        self, to, subject, body_text, body_html, cc, bcc, attachments, message_id, custom_headers
    ) -> Dict[str, Any]:
        """
        Construye payload genérico
        """
        
        payload = {
            "from": {
                "email": self.from_email,
                "name": self.from_name
            },
            "to": [{"email": email} for email in to],
            "subject": subject,
            "content": {
                "text": body_text,
                "html": body_html
            }
        }
        
        if cc:
            payload["cc"] = [{"email": email} for email in cc]
        if bcc:
            payload["bcc"] = [{"email": email} for email in bcc]
        
        if custom_headers:
            payload["headers"] = custom_headers
        
        if attachments:
            payload["attachments"] = attachments
        
        return payload
    
    async def _send_generic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía via API genérica
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.custom_headers
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.endpoint,
                json=payload,
                headers=headers
            )
            
            if 200 <= response.status_code < 300:
                try:
                    result = response.json()
                    return {
                        "success": True,
                        "response": result,
                        "status_code": response.status_code
                    }
                except:
                    return {
                        "success": True,
                        "response": response.text,
                        "status_code": response.status_code
                    }
            else:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code} - {response.text}",
                    "status_code": response.status_code
                }
    
    def get_sender_info(self) -> Dict[str, Any]:
        """
        Obtiene información del sender API
        """
        return {
            "provider_type": f"api_{self.provider_type}",
            "endpoint": self.endpoint,
            "from_email": self.from_email,
            "from_name": self.from_name,
            "timeout": self.timeout,
            "features": {
                "html_support": True,
                "attachments": self.provider_type in ['sendgrid', 'mailgun'],
                "cc_bcc": True,
                "custom_headers": True,
                "templates": self.provider_type == 'sendgrid'
            }
        }
    
    async def test_connection(self) -> bool:
        """
        Prueba conexión API
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                **self.custom_headers
            }
            
            # Test endpoint específico según proveedor
            test_endpoint = self.endpoint
            if self.provider_type == 'sendgrid':
                test_endpoint = f"{self.endpoint}/v3/user/account"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(test_endpoint, headers=headers)
                return 200 <= response.status_code < 500  # 4xx = auth issue, still "connected"
                
        except Exception as e:
            logging.error(f"API connection test failed: {e}")
            return False