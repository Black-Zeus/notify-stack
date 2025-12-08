# =============================================================================
# Stacks/bkn_celery/providers/mailgun.py
# =============================================================================
# Implementación Mailgun provider usando API v3

import httpx
from typing import Dict, Any, List
import logging
from datetime import datetime
import base64

from .base import BaseProvider, EmailMessage, SendResult, ProviderConnectionError, ProviderAuthError

logger = logging.getLogger(__name__)


class MailgunProvider(BaseProvider):
    """Provider para envío de emails vía Mailgun API v3"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Mailgun configuration
        self.api_key = config.get('api_key')
        self.domain = config.get('domain')
        self.endpoint = config.get('endpoint', 'https://api.mailgun.net/v3')
        
        # Construir URL completa
        if self.domain:
            self.send_url = f"{self.endpoint}/{self.domain}/messages"
        else:
            self.send_url = None
        
        if not self.api_key or not self.domain:
            raise ValueError(f"Mailgun API key and domain required for {self.provider_name}")
    
    async def validate_config(self) -> bool:
        """Valida la configuración de Mailgun"""
        if not self.api_key:
            raise ValueError("Mailgun API key is required")
        
        if not self.domain:
            raise ValueError("Mailgun domain is required")
        
        return True
    
    async def send(self, message: EmailMessage) -> SendResult:
        """
        Envía email vía Mailgun API
        
        Args:
            message: EmailMessage con los datos del email
            
        Returns:
            SendResult con resultado del envío
        """
        try:
            # Validar mensaje
            self.validate_message(message)
            
            # Construir form data de Mailgun
            form_data, files = self._build_mailgun_data(message)
            
            # Enviar via API
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.send_url,
                    auth=('api', self.api_key),
                    data=form_data,
                    files=files if files else None
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    message_id = response_data.get('id', message.message_id)
                    
                    logger.info(
                        f"Email sent via Mailgun [{self.provider_name}]: "
                        f"message_id={message_id}, recipients={len(message.to)}"
                    )
                    
                    return SendResult(
                        success=True,
                        message_id=message_id,
                        provider=self.provider_name,
                        response_data=response_data,
                        timestamp=datetime.utcnow().isoformat()
                    )
                else:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get('message', response.text)
                    
                    logger.error(
                        f"Mailgun error [{self.provider_name}]: "
                        f"{response.status_code} - {error_msg}"
                    )
                    
                    return SendResult(
                        success=False,
                        provider=self.provider_name,
                        error=f"Mailgun error ({response.status_code}): {error_msg}",
                        response_data=error_data,
                        timestamp=datetime.utcnow().isoformat()
                    )
                    
        except httpx.TimeoutException as e:
            logger.error(f"Mailgun timeout [{self.provider_name}]: {e}")
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=f"Request timeout: {str(e)}",
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Unexpected Mailgun error [{self.provider_name}]: {e}")
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=f"Unexpected error: {str(e)}",
                timestamp=datetime.utcnow().isoformat()
            )
    
    def _build_mailgun_data(self, message: EmailMessage) -> tuple[Dict[str, Any], List]:
        """Construye form data para Mailgun API"""
        
        # From address
        from_email, from_name = self.get_from_address(message)
        from_header = f"{from_name} <{from_email}>" if from_name else from_email
        
        # Form data básico
        form_data = {
            'from': from_header,
            'to': message.to,
            'subject': message.subject
        }
        
        # CC
        if message.cc:
            form_data['cc'] = message.cc
        
        # BCC
        if message.bcc:
            form_data['bcc'] = message.bcc
        
        # Reply-To
        if message.reply_to:
            form_data['h:Reply-To'] = message.reply_to
        
        # Body text
        if message.body_text:
            form_data['text'] = message.body_text
        
        # Body HTML
        if message.body_html:
            form_data['html'] = message.body_html
        
        # Custom headers (prefijo h:)
        if message.custom_headers:
            for key, value in message.custom_headers.items():
                form_data[f'h:{key}'] = value
        
        # Variables/tags (metadata)
        if message.message_id:
            form_data['v:message_id'] = message.message_id
        
        # Tracking
        if self.features.get('tracking', True):
            form_data['o:tracking'] = 'yes'
            form_data['o:tracking-clicks'] = 'yes'
            form_data['o:tracking-opens'] = 'yes'
        
        # Attachments como files multipart
        files = []
        if message.attachments:
            for idx, attachment in enumerate(message.attachments):
                filename = attachment.get('filename', f'attachment_{idx}')
                content = attachment.get('content')
                content_type = attachment.get('content_type', 'application/octet-stream')
                
                if content:
                    # Mailgun espera tupla (filename, file_content, content_type)
                    if isinstance(content, bytes):
                        file_content = content
                    else:
                        file_content = content.encode('utf-8')
                    
                    files.append(
                        ('attachment', (filename, file_content, content_type))
                    )
        
        return form_data, files
    
    async def test_connection(self) -> bool:
        """Prueba la conexión a Mailgun verificando dominio"""
        try:
            # Endpoint para verificar dominio
            url = f"{self.endpoint}/domains/{self.domain}"
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    url,
                    auth=('api', self.api_key)
                )
                
                if response.status_code == 200:
                    domain_info = response.json().get('domain', {})
                    state = domain_info.get('state', 'unknown')
                    
                    logger.info(
                        f"Mailgun connection test successful [{self.provider_name}]: "
                        f"domain={self.domain}, state={state}"
                    )
                    return True
                else:
                    logger.error(
                        f"Mailgun connection test failed [{self.provider_name}]: "
                        f"{response.status_code}"
                    )
                    return False
                    
        except Exception as e:
            logger.error(f"Mailgun connection test failed [{self.provider_name}]: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del dominio (opcional)"""
        try:
            url = f"{self.endpoint}/{self.domain}/stats/total"
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    url,
                    auth=('api', self.api_key),
                    params={'event': 'accepted'}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to get Mailgun stats: {response.status_code}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error getting Mailgun stats: {e}")
            return {}