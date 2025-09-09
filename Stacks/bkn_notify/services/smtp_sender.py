"""
SMTP sender service
Maneja envío de emails via SMTP con soporte para attachments y HTML
"""

import ssl
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, formatdate
from typing import Dict, Any, List, Optional
from datetime import datetime
import base64

from constants import SMTP_TIMEOUT


class SMTPSender:
    """
    Cliente SMTP para envío de emails
    """
    
    def __init__(self, provider_config: Dict[str, Any]):
        """
        Inicializa SMTP sender con configuración del proveedor
        
        Args:
            provider_config: Dict con host, port, username, password, use_tls, use_ssl
        """
        self.config = provider_config
        self.host = provider_config['host']
        self.port = int(provider_config['port'])
        self.username = provider_config['username']
        self.password = provider_config['password']
        self.use_tls = provider_config.get('use_tls', True)
        self.use_ssl = provider_config.get('use_ssl', False)
        self.timeout = provider_config.get('timeout', SMTP_TIMEOUT)
        
        # Configuración adicional
        self.from_name = provider_config.get('from_name', '')
        self.reply_to = provider_config.get('reply_to', '')
        self.return_path = provider_config.get('return_path', '')
    
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
        Envía email via SMTP
        
        Returns:
            Dict con resultado del envío: success, message_id, provider_response, etc.
        """
        
        start_time = datetime.now()
        
        try:
            # Validar parámetros
            self._validate_send_params(to, subject, body_text, body_html)
            
            # Construir mensaje MIME
            message = await self._build_mime_message(
                to=to,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
                message_id=message_id,
                custom_headers=custom_headers
            )
            
            # Obtener lista completa de destinatarios
            all_recipients = to + (cc or []) + (bcc or [])
            
            # Enviar via SMTP
            smtp_response = await self._send_via_smtp(message, all_recipients)
            
            # Calcular tiempo de envío
            end_time = datetime.now()
            send_duration = (end_time - start_time).total_seconds()
            
            # Construir respuesta exitosa
            result = {
                "success": True,
                "message_id": message_id,
                "provider": "smtp",
                "provider_config": self.host,
                "recipients_count": len(all_recipients),
                "send_duration": send_duration,
                "smtp_response": smtp_response,
                "sent_at": end_time.isoformat()
            }
            
            logging.info(f"Email sent successfully via SMTP to {len(all_recipients)} recipients")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            send_duration = (end_time - start_time).total_seconds()
            
            logging.error(f"SMTP send failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "provider": "smtp",
                "provider_config": self.host,
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
        
        # Validar formato de emails
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        for email in to:
            if not re.match(email_pattern, email):
                raise ValueError(f"Invalid email format: {email}")
    
    async def _build_mime_message(
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
    ) -> MIMEMultipart:
        """
        Construye mensaje MIME completo
        """
        
        # Crear mensaje base
        if body_html and body_text:
            message = MIMEMultipart('alternative')
        elif attachments:
            message = MIMEMultipart('mixed')
        else:
            message = MIMEMultipart()
        
        # Headers básicos
        from_addr = formataddr((self.from_name, self.username)) if self.from_name else self.username
        message['From'] = from_addr
        message['To'] = ', '.join(to)
        message['Subject'] = subject
        message['Date'] = formatdate(localtime=True)
        
        # Headers opcionales
        if cc:
            message['Cc'] = ', '.join(cc)
        
        if self.reply_to:
            message['Reply-To'] = self.reply_to
        
        if self.return_path:
            message['Return-Path'] = self.return_path
        
        # Message-ID personalizado
        if message_id:
            message['Message-ID'] = f"<{message_id}@{self.host}>"
        
        # Headers personalizados
        if custom_headers:
            for key, value in custom_headers.items():
                message[key] = value
        
        # Cuerpo del mensaje
        if body_text and body_html:
            # Mensaje multipart/alternative
            text_part = MIMEText(body_text, 'plain', 'utf-8')
            html_part = MIMEText(body_html, 'html', 'utf-8')
            
            message.attach(text_part)
            message.attach(html_part)
        elif body_html:
            html_part = MIMEText(body_html, 'html', 'utf-8')
            message.attach(html_part)
        elif body_text:
            text_part = MIMEText(body_text, 'plain', 'utf-8')
            message.attach(text_part)
        
        # Attachments
        if attachments:
            for attachment in attachments:
                await self._add_attachment(message, attachment)
        
        return message
    
    async def _add_attachment(self, message: MIMEMultipart, attachment: Dict[str, Any]):
        """
        Agrega attachment al mensaje MIME
        """
        try:
            filename = attachment['filename']
            content = attachment['content']
            content_type = attachment.get('content_type', 'application/octet-stream')
            
            # Decodificar contenido base64
            if isinstance(content, str):
                file_data = base64.b64decode(content)
            else:
                file_data = content
            
            # Crear parte MIME para attachment
            part = MIMEBase(*content_type.split('/', 1))
            part.set_payload(file_data)
            encoders.encode_base64(part)
            
            # Headers del attachment
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{filename}"'
            )
            
            message.attach(part)
            
        except Exception as e:
            logging.error(f"Error adding attachment {attachment.get('filename', 'unknown')}: {e}")
            raise ValueError(f"Invalid attachment: {e}")
    
    async def _send_via_smtp(self, message: MIMEMultipart, recipients: List[str]) -> Dict[str, Any]:
        """
        Envía mensaje via protocolo SMTP
        """
        smtp_client = None
        
        try:
            # Crear conexión SMTP
            if self.use_ssl:
                # SSL directo (puerto 465)
                context = ssl.create_default_context()
                smtp_client = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
            else:
                # SMTP estándar
                smtp_client = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                
                # STARTTLS si está habilitado
                if self.use_tls:
                    smtp_client.starttls()
            
            # Autenticación
            smtp_client.login(self.username, self.password)
            
            # Enviar mensaje
            smtp_response = smtp_client.send_message(message, to_addrs=recipients)
            
            return {
                "smtp_server": f"{self.host}:{self.port}",
                "authentication": "successful",
                "delivery_status": "accepted",
                "response": str(smtp_response) if smtp_response else "250 OK"
            }
            
        except smtplib.SMTPAuthenticationError as e:
            raise Exception(f"SMTP authentication failed: {e}")
        except smtplib.SMTPRecipientsRefused as e:
            raise Exception(f"Recipients refused: {e}")
        except smtplib.SMTPDataError as e:
            raise Exception(f"SMTP data error: {e}")
        except smtplib.SMTPException as e:
            raise Exception(f"SMTP error: {e}")
        except Exception as e:
            raise Exception(f"SMTP connection error: {e}")
        finally:
            # Cerrar conexión
            if smtp_client:
                try:
                    smtp_client.quit()
                except:
                    pass
    
    def get_sender_info(self) -> Dict[str, Any]:
        """
        Obtiene información del sender SMTP
        """
        return {
            "provider_type": "smtp",
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "use_tls": self.use_tls,
            "use_ssl": self.use_ssl,
            "timeout": self.timeout,
            "from_name": self.from_name,
            "features": {
                "html_support": True,
                "attachments": True,
                "cc_bcc": True,
                "custom_headers": True,
                "message_id": True
            }
        }
    
    async def test_connection(self) -> bool:
        """
        Prueba conexión SMTP
        """
        try:
            smtp_client = None
            
            if self.use_ssl:
                context = ssl.create_default_context()
                smtp_client = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
            else:
                smtp_client = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                if self.use_tls:
                    smtp_client.starttls()
            
            smtp_client.login(self.username, self.password)
            smtp_client.quit()
            
            return True
            
        except Exception as e:
            logging.error(f"SMTP connection test failed: {e}")
            return False