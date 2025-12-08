# =============================================================================
# Stacks/bkn_celery/providers/smtp.py
# =============================================================================
# Implementación SMTP provider usando smtplib

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, formatdate, make_msgid
from typing import Dict, Any
import logging
from datetime import datetime

from .base import BaseProvider, EmailMessage, SendResult, ProviderConnectionError, ProviderAuthError

logger = logging.getLogger(__name__)


class SMTPProvider(BaseProvider):
    """Provider para envío de emails vía SMTP"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # SMTP configuration
        self.host = config.get('host')
        self.port = config.get('port', 587)
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.use_tls = config.get('use_tls', True)
        self.use_ssl = config.get('use_ssl', False)
        self.verify_certificate = config.get('verify_certificate', True)
        
        # Headers configuration
        self.reply_to = config.get('reply_to')
        self.return_path = config.get('return_path')
        
        if not self.host:
            raise ValueError(f"SMTP host not configured for {self.provider_name}")
    
    async def validate_config(self) -> bool:
        """Valida la configuración SMTP"""
        if not self.host:
            raise ValueError("SMTP host is required")
        
        if not isinstance(self.port, int) or self.port <= 0:
            raise ValueError(f"Invalid SMTP port: {self.port}")
        
        return True
    
    async def send(self, message: EmailMessage) -> SendResult:
        """
        Envía email vía SMTP
        
        Args:
            message: EmailMessage con los datos del email
            
        Returns:
            SendResult con resultado del envío
        """
        try:
            # Validar mensaje
            self.validate_message(message)
            
            # Construir MIME message
            mime_msg = self._build_mime_message(message)
            
            # Enviar via SMTP
            response = await self._send_smtp(mime_msg, message)
            
            return SendResult(
                success=True,
                message_id=message.message_id,
                provider=self.provider_name,
                response_data=response,
                timestamp=datetime.utcnow().isoformat()
            )
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP auth error [{self.provider_name}]: {e}")
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=f"Authentication failed: {str(e)}",
                timestamp=datetime.utcnow().isoformat()
            )
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error [{self.provider_name}]: {e}")
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=f"SMTP error: {str(e)}",
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Unexpected error [{self.provider_name}]: {e}")
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=f"Unexpected error: {str(e)}",
                timestamp=datetime.utcnow().isoformat()
            )
    
    def _build_mime_message(self, message: EmailMessage) -> MIMEMultipart:
        """Construye mensaje MIME desde EmailMessage"""
        
        # Crear mensaje multipart
        if message.body_html and message.body_text:
            mime_msg = MIMEMultipart('alternative')
        elif message.attachments:
            mime_msg = MIMEMultipart('mixed')
        else:
            mime_msg = MIMEMultipart()
        
        # From address
        from_email, from_name = self.get_from_address(message)
        mime_msg['From'] = formataddr((from_name, from_email))
        
        # To addresses
        mime_msg['To'] = ', '.join(message.to)
        
        # CC addresses
        if message.cc:
            mime_msg['Cc'] = ', '.join(message.cc)
        
        # Subject
        mime_msg['Subject'] = message.subject
        
        # Message ID
        if message.message_id:
            mime_msg['Message-ID'] = f"<{message.message_id}@{self.host}>"
        else:
            mime_msg['Message-ID'] = make_msgid(domain=self.host)
        
        # Date
        mime_msg['Date'] = formatdate(localtime=True)
        
        # Reply-To
        reply_to = message.reply_to or self.reply_to
        if reply_to:
            mime_msg['Reply-To'] = reply_to
        
        # Return-Path
        if self.return_path:
            mime_msg['Return-Path'] = self.return_path
        
        # Custom headers
        if message.custom_headers:
            for key, value in message.custom_headers.items():
                mime_msg[key] = value
        
        # Body text
        if message.body_text:
            mime_msg.attach(MIMEText(message.body_text, 'plain', 'utf-8'))
        
        # Body HTML
        if message.body_html:
            mime_msg.attach(MIMEText(message.body_html, 'html', 'utf-8'))
        
        # Attachments
        if message.attachments:
            for attachment in message.attachments:
                self._add_attachment(mime_msg, attachment)
        
        return mime_msg
    
    def _add_attachment(self, mime_msg: MIMEMultipart, attachment: Dict[str, Any]):
        """Añade un attachment al mensaje MIME"""
        
        filename = attachment.get('filename', 'attachment')
        content = attachment.get('content')
        content_type = attachment.get('content_type', 'application/octet-stream')
        
        if not content:
            logger.warning(f"Skipping attachment without content: {filename}")
            return
        
        # Crear parte MIME
        part = MIMEBase(*content_type.split('/', 1))
        part.set_payload(content)
        encoders.encode_base64(part)
        
        # Headers del attachment
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="{filename}"'
        )
        
        mime_msg.attach(part)
    
    async def _send_smtp(self, mime_msg: MIMEMultipart, message: EmailMessage) -> Dict[str, Any]:
        """Envía el mensaje MIME via SMTP"""
        
        # Preparar lista de destinatarios
        recipients = message.to.copy()
        if message.cc:
            recipients.extend(message.cc)
        if message.bcc:
            recipients.extend(message.bcc)
        
        # Determinar contexto SSL
        context = None
        if self.use_tls or self.use_ssl:
            context = ssl.create_default_context()
            if not self.verify_certificate:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
        
        # Conectar y enviar
        smtp_conn = None
        try:
            if self.use_ssl:
                # Conexión SSL desde el inicio
                smtp_conn = smtplib.SMTP_SSL(
                    self.host,
                    self.port,
                    timeout=self.timeout,
                    context=context
                )
            else:
                # Conexión normal, luego STARTTLS si está habilitado
                smtp_conn = smtplib.SMTP(
                    self.host,
                    self.port,
                    timeout=self.timeout
                )
                
                if self.use_tls:
                    smtp_conn.starttls(context=context)
            
            # Autenticación si hay credenciales
            if self.username and self.password:
                smtp_conn.login(self.username, self.password)
            
            # Enviar mensaje
            result = smtp_conn.send_message(mime_msg, to_addrs=recipients)
            
            logger.info(
                f"Email sent via SMTP [{self.provider_name}]: "
                f"{len(recipients)} recipients, message_id={mime_msg['Message-ID']}"
            )
            
            return {
                'recipients': recipients,
                'refused': result,  # Dict de destinatarios rechazados
                'message_id': mime_msg['Message-ID']
            }
            
        finally:
            if smtp_conn:
                try:
                    smtp_conn.quit()
                except:
                    pass
    
    async def test_connection(self) -> bool:
        """Prueba la conexión SMTP"""
        try:
            context = None
            if self.use_tls or self.use_ssl:
                context = ssl.create_default_context()
                if not self.verify_certificate:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
            
            if self.use_ssl:
                smtp = smtplib.SMTP_SSL(
                    self.host,
                    self.port,
                    timeout=self.timeout,
                    context=context
                )
            else:
                smtp = smtplib.SMTP(
                    self.host,
                    self.port,
                    timeout=self.timeout
                )
                if self.use_tls:
                    smtp.starttls(context=context)
            
            if self.username and self.password:
                smtp.login(self.username, self.password)
            
            smtp.quit()
            
            logger.info(f"SMTP connection test successful [{self.provider_name}]")
            return True
            
        except Exception as e:
            logger.error(f"SMTP connection test failed [{self.provider_name}]: {e}")
            return False