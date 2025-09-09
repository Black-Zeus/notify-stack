"""
SMTP testing service
Prueba conectividad y configuración de proveedores SMTP sin enviar emails
"""

import ssl
import socket
import smtplib
import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

from constants import SMTP_TIMEOUT


async def test_smtp_connectivity(provider_config: Dict[str, Any], timeout: int = SMTP_TIMEOUT) -> Dict[str, Any]:
    """
    Prueba conectividad SMTP completa sin enviar emails
    
    Args:
        provider_config: Configuración del proveedor SMTP
        timeout: Timeout en segundos para la conexión
        
    Returns:
        Dict con resultado del test: status, message, response_time, details
    """
    
    start_time = datetime.now()
    
    try:
        # Validar configuración requerida
        required_fields = ['host', 'port', 'username', 'password']
        missing_fields = [field for field in required_fields if not provider_config.get(field)]
        
        if missing_fields:
            return {
                "status": "error",
                "message": f"Missing configuration fields: {missing_fields}",
                "response_time": 0,
                "details": {"missing_fields": missing_fields}
            }
        
        # Ejecutar test en thread pool para no bloquear
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            _test_smtp_sync, 
            provider_config, 
            timeout
        )
        
        # Calcular tiempo de respuesta
        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()
        result["response_time"] = response_time
        
        logging.info(f"SMTP test completed for {provider_config.get('host')}: {result['status']}")
        return result
        
    except Exception as e:
        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()
        
        logging.error(f"SMTP test failed for {provider_config.get('host')}: {e}")
        return {
            "status": "error",
            "message": f"Test execution failed: {str(e)}",
            "response_time": response_time,
            "details": {"exception": type(e).__name__}
        }


def _test_smtp_sync(provider_config: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """
    Ejecuta test SMTP síncrono (para thread pool)
    """
    
    host = provider_config['host']
    port = int(provider_config['port'])
    username = provider_config['username']
    password = provider_config['password']
    use_tls = provider_config.get('use_tls', True)
    use_ssl = provider_config.get('use_ssl', False)
    
    smtp_client = None
    test_details = {}
    
    try:
        # Test 1: Conexión TCP básica
        test_details["tcp_connection"] = _test_tcp_connection(host, port, timeout)
        if not test_details["tcp_connection"]["success"]:
            return {
                "status": "error",
                "message": f"TCP connection failed to {host}:{port}",
                "details": test_details
            }
        
        # Test 2: Crear cliente SMTP
        if use_ssl:
            # Conexión SSL directa (puerto 465)
            context = ssl.create_default_context()
            smtp_client = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
            test_details["ssl_connection"] = {"success": True, "type": "direct_ssl"}
        else:
            # Conexión SMTP estándar
            smtp_client = smtplib.SMTP(host, port, timeout=timeout)
            test_details["smtp_connection"] = {"success": True}
            
            # Test 3: STARTTLS si está habilitado
            if use_tls:
                smtp_client.starttls()
                test_details["starttls"] = {"success": True}
        
        # Test 4: Autenticación
        try:
            smtp_client.login(username, password)
            test_details["authentication"] = {"success": True, "username": username}
        except smtplib.SMTPAuthenticationError as e:
            return {
                "status": "error",
                "message": f"Authentication failed: {str(e)}",
                "details": test_details
            }
        
        # Test 5: Verificar capacidades del servidor
        capabilities = _get_smtp_capabilities(smtp_client)
        test_details["capabilities"] = capabilities
        
        # Test 6: Verificar que puede enviar (MAIL FROM sin TO)
        try:
            smtp_client.mail(username)
            smtp_client.rset()  # Reset para limpiar
            test_details["mail_from_test"] = {"success": True}
        except Exception as e:
            test_details["mail_from_test"] = {"success": False, "error": str(e)}
        
        return {
            "status": "healthy",
            "message": f"SMTP server {host}:{port} is accessible and authenticated",
            "details": test_details
        }
        
    except smtplib.SMTPConnectError as e:
        return {
            "status": "error",
            "message": f"Failed to connect to SMTP server: {str(e)}",
            "details": test_details
        }
    except smtplib.SMTPServerDisconnected as e:
        return {
            "status": "error", 
            "message": f"SMTP server disconnected: {str(e)}",
            "details": test_details
        }
    except smtplib.SMTPException as e:
        return {
            "status": "error",
            "message": f"SMTP error: {str(e)}",
            "details": test_details
        }
    except ssl.SSLError as e:
        return {
            "status": "error",
            "message": f"SSL/TLS error: {str(e)}",
            "details": test_details
        }
    except socket.timeout:
        return {
            "status": "error",
            "message": f"Connection timeout after {timeout} seconds",
            "details": test_details
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "details": test_details
        }
    finally:
        # Limpiar conexión
        if smtp_client:
            try:
                smtp_client.quit()
            except:
                pass


def _test_tcp_connection(host: str, port: int, timeout: int) -> Dict[str, Any]:
    """
    Prueba conexión TCP básica al servidor
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            return {"success": True, "message": "TCP connection successful"}
        else:
            return {"success": False, "message": f"TCP connection failed with code {result}"}
            
    except socket.gaierror as e:
        return {"success": False, "message": f"DNS resolution failed: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"TCP test error: {str(e)}"}


def _get_smtp_capabilities(smtp_client: smtplib.SMTP) -> Dict[str, Any]:
    """
    Obtiene capacidades del servidor SMTP
    """
    try:
        capabilities = {}
        
        # Obtener respuesta EHLO
        if hasattr(smtp_client, 'ehlo_resp') and smtp_client.ehlo_resp:
            ehlo_features = smtp_client.ehlo_resp.decode('utf-8').split('\n')[1:]
            capabilities["ehlo_features"] = [feat.strip() for feat in ehlo_features]
        
        # Verificar extensiones específicas
        capabilities["supports_tls"] = smtp_client.has_extn('STARTTLS')
        capabilities["supports_auth"] = smtp_client.has_extn('AUTH')
        capabilities["supports_size"] = smtp_client.has_extn('SIZE')
        capabilities["supports_pipelining"] = smtp_client.has_extn('PIPELINING')
        
        # Obtener límite de tamaño si está disponible
        if capabilities["supports_size"]:
            size_limit = smtp_client.ehlo_resp.decode('utf-8')
            import re
            size_match = re.search(r'SIZE\s+(\d+)', size_limit)
            if size_match:
                capabilities["max_message_size"] = int(size_match.group(1))
        
        return capabilities
        
    except Exception as e:
        return {"error": f"Failed to get capabilities: {str(e)}"}


async def test_smtp_delivery_simulation(provider_config: Dict[str, Any], test_recipient: str = None) -> Dict[str, Any]:
    """
    Simula envío de email sin enviarlo realmente
    Útil para probar el pipeline completo de preparación
    """
    
    try:
        # Test de conectividad primero
        connectivity_result = await test_smtp_connectivity(provider_config)
        
        if connectivity_result["status"] != "healthy":
            return {
                "status": "error",
                "message": "Connectivity test failed",
                "connectivity_test": connectivity_result
            }
        
        # Simular preparación de mensaje
        test_message = _prepare_test_message(test_recipient or "test@example.com")
        
        # Validar mensaje
        validation_result = _validate_message_format(test_message)
        
        return {
            "status": "healthy",
            "message": "Delivery simulation successful",
            "connectivity_test": connectivity_result,
            "message_validation": validation_result,
            "simulated_message": {
                "size": len(test_message),
                "headers_count": test_message.count('\n'),
                "has_body": '\n\n' in test_message
            }
        }
        
    except Exception as e:
        logging.error(f"SMTP delivery simulation failed: {e}")
        return {
            "status": "error",
            "message": f"Delivery simulation failed: {str(e)}"
        }


def _prepare_test_message(recipient: str) -> str:
    """
    Prepara mensaje de prueba simulado
    """
    message = f"""From: test@notify-system.local
To: {recipient}
Subject: SMTP Test Message - Do Not Reply
Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')}
Message-ID: <test-{datetime.now().timestamp()}@notify-system.local>
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

This is a test message from the Notify API system.
This message was not actually sent, only prepared for testing.

System: notify-api
Test Type: SMTP Connectivity
Timestamp: {datetime.now().isoformat()}
"""
    return message


def _validate_message_format(message: str) -> Dict[str, Any]:
    """
    Valida formato básico del mensaje
    """
    validation = {
        "has_from": "From:" in message,
        "has_to": "To:" in message,
        "has_subject": "Subject:" in message,
        "has_date": "Date:" in message,
        "has_message_id": "Message-ID:" in message,
        "has_body_separator": "\n\n" in message,
        "valid_encoding": True
    }
    
    try:
        message.encode('utf-8')
    except UnicodeEncodeError:
        validation["valid_encoding"] = False
    
    validation["all_valid"] = all(validation.values())
    
    return validation


def get_smtp_test_summary(provider_configs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Genera resumen de configuraciones SMTP para testing
    """
    summary = {
        "total_providers": len(provider_configs),
        "smtp_providers": 0,
        "providers": {}
    }
    
    for name, config in provider_configs.items():
        if config.get("type") == "smtp":
            summary["smtp_providers"] += 1
            summary["providers"][name] = {
                "host": config.get("host"),
                "port": config.get("port"),
                "uses_tls": config.get("use_tls", True),
                "uses_ssl": config.get("use_ssl", False),
                "has_credentials": bool(config.get("username") and config.get("password"))
            }
    
    return summary