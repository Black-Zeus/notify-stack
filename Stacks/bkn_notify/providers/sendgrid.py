# =============================================================================
# Stacks/bkn_celery/providers/sendgrid.py
# =============================================================================
# Implementación SendGrid provider usando API v3

import httpx
from typing import Dict, Any, List
import logging
from datetime import datetime
import base64

from .base import BaseProvider, EmailMessage, SendResult, ProviderConnectionError, ProviderAuthError

logger = logging.getLogger(__name__)


class SendGridProvider(BaseProvider):
    """Provider para envío de emails vía SendGrid API v3"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # SendGrid configuration
        self.api_key = config.get('api_key')
        self.endpoint = config.get('endpoint', 'https://api.sendgrid.com/v3/mail/send')
        
        # Tracking settings
        tracking_config = config.get('tracking_settings', {})
        self.click_tracking = tracking_config.get('click_tracking', True)
        self.open_tracking = tracking_config.get('open_tracking', True)
        self.subscription_tracking = tracking_config.get('subscription_tracking', False)
        
        if not self.api_key:
            raise ValueError(f"SendGrid API key not configured for {self.provider_name}")
    
    async def validate_config(self) -> bool:
        """Valida la configuración de SendGrid"""
        if not self.api_key:
            raise ValueError("SendGrid API key is required")
        
        if not self.api_key.startswith('SG.'):
            logger.warning("SendGrid API key should start with 'SG.'")
        
        return True
    
    async def send(self, message: EmailMessage) -> SendResult:
        """
        Envía email vía SendGrid API
        
        Args:
            message: EmailMessage con los datos del email
            
        Returns:
            SendResult con resultado del envío
        """
        try:
            # Validar mensaje
            self.validate_message(message)
            
            # Construir payload de SendGrid
            payload = self._build_sendgrid_payload(message)
            
            # Enviar via API
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json=payload
                )
                
                # SendGrid retorna 202 Accepted en éxito
                if response.status_code == 202:
                    # SendGrid no retorna message_id en body, está en header X-Message-Id
                    message_id = response.headers.get('X-Message-Id', message.message_id)
                    
                    logger.info(
                        f"Email sent via SendGrid [{self.provider_name}]: "
                        f"message_id={message_id}, recipients={len(message.to)}"
                    )
                    
                    return SendResult(
                        success=True,
                        message_id=message_id,
                        provider=self.provider_name,
                        response_data={
                            'message_id': message_id,
                            'status_code': response.status_code
                        },
                        timestamp=datetime.utcnow().isoformat()
                    )
                else:
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get('errors', [{}])[0].get('message', response.text)
                    
                    logger.error(
                        f"SendGrid error [{self.provider_name}]: "
                        f"{response.status_code} - {error_msg}"
                    )
                    
                    return SendResult(
                        success=False,
                        provider=self.provider_name,
                        error=f"SendGrid error ({response.status_code}): {error_msg}",
                        response_data=error_data,
                        timestamp=datetime.utcnow().isoformat()
                    )
                    
        except httpx.TimeoutException as e:
            logger.error(f"SendGrid timeout [{self.provider_name}]: {e}")
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=f"Request timeout: {str(e)}",
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Unexpected SendGrid error [{self.provider_name}]: {e}")
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=f"Unexpected error: {str(e)}",
                timestamp=datetime.utcnow().isoformat()
            )
    
    def _build_sendgrid_payload(self, message: EmailMessage) -> Dict[str, Any]:
        """Construye el payload JSON para SendGrid API v3"""
        
        # From address
        from_email, from_name = self.get_from_address(message)
        
        payload = {
            'personalizations': [
                {
                    'to': [{'email': email} for email in message.to]
                }
            ],
            'from': {
                'email': from_email,
                'name': from_name
            },
            'subject': message.subject,
            'content': []
        }
        
        # CC
        if message.cc:
            payload['personalizations'][0]['cc'] = [
                {'email': email} for email in message.cc
            ]
        
        # BCC
        if message.bcc:
            payload['personalizations'][0]['bcc'] = [
                {'email': email} for email in message.bcc
            ]
        
        # Reply-To
        if message.reply_to:
            payload['reply_to'] = {'email': message.reply_to}
        
        # Content (text/html)
        if message.body_text:
            payload['content'].append({
                'type': 'text/plain',
                'value': message.body_text
            })
        
        if message.body_html:
            payload['content'].append({
                'type': 'text/html',
                'value': message.body_html
            })
        
        # Attachments
        if message.attachments:
            payload['attachments'] = []
            for attachment in message.attachments:
                sg_attachment = self._build_attachment(attachment)
                if sg_attachment:
                    payload['attachments'].append(sg_attachment)
        
        # Tracking settings
        payload['tracking_settings'] = {
            'click_tracking': {'enable': self.click_tracking},
            'open_tracking': {'enable': self.open_tracking},
            'subscription_tracking': {'enable': self.subscription_tracking}
        }
        
        # Custom headers
        if message.custom_headers:
            payload['headers'] = message.custom_headers
        
        # Custom args (metadata)
        if message.message_id:
            payload['custom_args'] = {
                'message_id': message.message_id
            }
        
        return payload
    
    def _build_attachment(self, attachment: Dict[str, Any]) -> Dict[str, Any]:
        """Construye attachment para SendGrid"""
        
        filename = attachment.get('filename', 'attachment')
        content = attachment.get('content')
        content_type = attachment.get('content_type', 'application/octet-stream')
        
        if not content:
            logger.warning(f"Skipping attachment without content: {filename}")
            return None
        
        # SendGrid espera content en base64
        if isinstance(content, bytes):
            content_b64 = base64.b64encode(content).decode('utf-8')
        else:
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        return {
            'content': content_b64,
            'filename': filename,
            'type': content_type,
            'disposition': 'attachment'
        }
    
    async def test_connection(self) -> bool:
        """Prueba la conexión a SendGrid verificando API key"""
        try:
            # Endpoint para verificar API key
            url = 'https://api.sendgrid.com/v3/scopes'
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    url,
                    headers={'Authorization': f'Bearer {self.api_key}'}
                )
                
                if response.status_code == 200:
                    scopes = response.json().get('scopes', [])
                    logger.info(
                        f"SendGrid connection test successful [{self.provider_name}]: "
                        f"API key valid, scopes={len(scopes)}"
                    )
                    return True
                else:
                    logger.error(
                        f"SendGrid connection test failed [{self.provider_name}]: "
                        f"{response.status_code}"
                    )
                    return False
                    
        except Exception as e:
            logger.error(f"SendGrid connection test failed [{self.provider_name}]: {e}")
            return False