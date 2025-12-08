# =============================================================================
# Stacks/bkn_celery/providers/ses.py
# =============================================================================
# Implementación Amazon SES provider usando boto3

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from typing import Dict, Any, List
import logging
from datetime import datetime
import base64

from .base import BaseProvider, EmailMessage, SendResult, ProviderConnectionError, ProviderAuthError

logger = logging.getLogger(__name__)


class SESProvider(BaseProvider):
    """Provider para envío de emails vía Amazon SES"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # AWS SES configuration
        self.region = config.get('aws_region', config.get('region', 'us-east-1'))
        self.access_key_id = config.get('access_key_id')
        self.secret_access_key = config.get('secret_access_key')
        self.configuration_set = config.get('configuration_set')
        
        # SES specific config
        ses_config = config.get('ses', {})
        self.configuration_set = ses_config.get('configuration_set', self.configuration_set)
        
        # Initialize boto3 client
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Inicializa el cliente boto3 de SES"""
        try:
            self.client = boto3.client(
                'ses',
                region_name=self.region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key
            )
            logger.info(f"SES client initialized for region {self.region}")
        except Exception as e:
            logger.error(f"Failed to initialize SES client: {e}")
            raise ProviderConnectionError(f"SES client initialization failed: {e}", provider=self.provider_name)
    
    async def validate_config(self) -> bool:
        """Valida la configuración de SES"""
        if not self.access_key_id or not self.secret_access_key:
            raise ValueError("SES access_key_id and secret_access_key are required")
        
        if not self.region:
            raise ValueError("SES region is required")
        
        return True
    
    async def send(self, message: EmailMessage) -> SendResult:
        """
        Envía email vía Amazon SES
        
        Args:
            message: EmailMessage con los datos del email
            
        Returns:
            SendResult con resultado del envío
        """
        try:
            # Validar mensaje
            self.validate_message(message)
            
            # Construir request de SES
            ses_request = self._build_ses_request(message)
            
            # Enviar via SES
            response = self.client.send_email(**ses_request)
            
            message_id = response.get('MessageId')
            
            logger.info(
                f"Email sent via SES [{self.provider_name}]: "
                f"message_id={message_id}, recipients={len(message.to)}"
            )
            
            return SendResult(
                success=True,
                message_id=message_id,
                provider=self.provider_name,
                response_data={
                    'message_id': message_id,
                    'request_id': response.get('ResponseMetadata', {}).get('RequestId')
                },
                timestamp=datetime.utcnow().isoformat()
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"SES ClientError [{self.provider_name}]: {error_code} - {error_message}")
            
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=f"SES error ({error_code}): {error_message}",
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Unexpected SES error [{self.provider_name}]: {e}")
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=f"Unexpected error: {str(e)}",
                timestamp=datetime.utcnow().isoformat()
            )
    
    def _build_ses_request(self, message: EmailMessage) -> Dict[str, Any]:
        """Construye el request para SES API"""
        
        # From address
        from_email, from_name = self.get_from_address(message)
        source = f'"{from_name}" <{from_email}>' if from_name else from_email
        
        # Destination
        destination = {'ToAddresses': message.to}
        
        if message.cc:
            destination['CcAddresses'] = message.cc
        
        if message.bcc:
            destination['BccAddresses'] = message.bcc
        
        # Message body
        body = {}
        
        if message.body_text:
            body['Text'] = {
                'Data': message.body_text,
                'Charset': 'UTF-8'
            }
        
        if message.body_html:
            body['Html'] = {
                'Data': message.body_html,
                'Charset': 'UTF-8'
            }
        
        # Construir request
        ses_request = {
            'Source': source,
            'Destination': destination,
            'Message': {
                'Subject': {
                    'Data': message.subject,
                    'Charset': 'UTF-8'
                },
                'Body': body
            }
        }
        
        # Reply-To
        if message.reply_to:
            ses_request['ReplyToAddresses'] = [message.reply_to]
        
        # Configuration Set (para tracking)
        if self.configuration_set:
            ses_request['ConfigurationSetName'] = self.configuration_set
        
        # Tags (si hay message_id)
        if message.message_id:
            ses_request['Tags'] = [
                {'Name': 'message_id', 'Value': message.message_id}
            ]
        
        return ses_request
    
    async def send_raw(self, message: EmailMessage) -> SendResult:
        """
        Envía email con attachments usando send_raw_email
        SES send_email no soporta attachments, usar send_raw_email
        """
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders
            
            # Construir MIME message
            mime_msg = MIMEMultipart()
            
            # Headers
            from_email, from_name = self.get_from_address(message)
            mime_msg['From'] = f'"{from_name}" <{from_email}>' if from_name else from_email
            mime_msg['To'] = ', '.join(message.to)
            mime_msg['Subject'] = message.subject
            
            if message.cc:
                mime_msg['Cc'] = ', '.join(message.cc)
            
            if message.reply_to:
                mime_msg['Reply-To'] = message.reply_to
            
            # Body
            if message.body_text:
                mime_msg.attach(MIMEText(message.body_text, 'plain', 'utf-8'))
            
            if message.body_html:
                mime_msg.attach(MIMEText(message.body_html, 'html', 'utf-8'))
            
            # Attachments
            if message.attachments:
                for attachment in message.attachments:
                    filename = attachment.get('filename', 'attachment')
                    content = attachment.get('content')
                    content_type = attachment.get('content_type', 'application/octet-stream')
                    
                    part = MIMEBase(*content_type.split('/', 1))
                    part.set_payload(content)
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    mime_msg.attach(part)
            
            # Enviar raw email
            destinations = message.to.copy()
            if message.cc:
                destinations.extend(message.cc)
            if message.bcc:
                destinations.extend(message.bcc)
            
            response = self.client.send_raw_email(
                Source=from_email,
                Destinations=destinations,
                RawMessage={'Data': mime_msg.as_string()},
                ConfigurationSetName=self.configuration_set if self.configuration_set else None
            )
            
            message_id = response.get('MessageId')
            
            logger.info(f"Raw email sent via SES [{self.provider_name}]: message_id={message_id}")
            
            return SendResult(
                success=True,
                message_id=message_id,
                provider=self.provider_name,
                response_data={'message_id': message_id},
                timestamp=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            logger.error(f"SES raw email error [{self.provider_name}]: {e}")
            return SendResult(
                success=False,
                provider=self.provider_name,
                error=str(e),
                timestamp=datetime.utcnow().isoformat()
            )
    
    async def test_connection(self) -> bool:
        """Prueba la conexión a SES"""
        try:
            # Verificar cuota de envío
            response = self.client.get_send_quota()
            
            max_send_rate = response.get('MaxSendRate', 0)
            sent_last_24_hours = response.get('SentLast24Hours', 0)
            
            logger.info(
                f"SES connection test successful [{self.provider_name}]: "
                f"MaxSendRate={max_send_rate}, SentLast24Hours={sent_last_24_hours}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"SES connection test failed [{self.provider_name}]: {e}")
            return False