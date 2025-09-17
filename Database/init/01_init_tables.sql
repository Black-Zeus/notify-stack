-- =============================================================================
-- NOTIFY-STACK - Database Schema Initialization
-- =============================================================================
-- Database/init/01_init_tables.sql
-- Esquema inicial para tracking y auditoría de notificaciones
-- Ejecutado automáticamente en el primer arranque de MySQL

-- =============================================================================
-- CONFIGURACIÓN INICIAL
-- =============================================================================

-- Usar charset UTF8 para soporte completo de caracteres
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- =============================================================================
-- TABLA: notifications
-- =============================================================================
-- Registro principal de cada notificación enviada

CREATE TABLE IF NOT EXISTS notifications (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    message_id VARCHAR(255) NOT NULL UNIQUE,
    
    -- Información del template
    template_id VARCHAR(100),
    template_version VARCHAR(20),
    
    -- Destinatarios
    to_email VARCHAR(500) NOT NULL,
    cc_emails JSON,
    bcc_emails JSON,
    
    -- Contenido
    subject VARCHAR(1000),
    body_text LONGTEXT,
    body_html LONGTEXT,
    
    -- Configuración de envío
    provider VARCHAR(50),
    routing_hint VARCHAR(100),
    priority ENUM('LOW', 'MEDIUM', 'HIGH') DEFAULT 'MEDIUM',
    
    -- Variables del template (JSON)
    params_json JSON,
    
    -- Metadatos
    idempotency_key VARCHAR(255),
    celery_task_id VARCHAR(255),
    
    -- Estados
    status ENUM('PENDING', 'PROCESSING', 'SENT', 'FAILED', 'REJECTED') DEFAULT 'PENDING',
    retry_count INT UNSIGNED DEFAULT 0,
    max_retries INT UNSIGNED DEFAULT 3,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Metadatos de origen
    source_ip VARCHAR(45),
    user_agent VARCHAR(500),
    api_key_hash VARCHAR(64),
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_message_id (message_id),
    KEY idx_status (status),
    KEY idx_created_at (created_at),
    KEY idx_to_email (to_email(100)),
    KEY idx_template_id (template_id),
    KEY idx_provider (provider),
    KEY idx_celery_task (celery_task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: notification_logs
-- =============================================================================
-- Log detallado de eventos y cambios de estado

CREATE TABLE IF NOT EXISTS notification_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    message_id VARCHAR(255) NOT NULL,
    
    -- Información del evento
    event_type VARCHAR(50) NOT NULL,
    event_status VARCHAR(50),
    
    -- Detalles del evento
    event_message TEXT,
    details_json JSON,
    
    -- Contexto técnico
    component VARCHAR(50), -- 'api', 'celery', 'smtp', etc.
    provider VARCHAR(50),
    
    -- Métricas
    processing_time_ms INT UNSIGNED,
    
    -- Timestamp
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    KEY idx_message_id (message_id),
    KEY idx_event_type (event_type),
    KEY idx_timestamp (timestamp),
    KEY idx_component (component),
    
    FOREIGN KEY (message_id) REFERENCES notifications(message_id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: notification_attachments
-- =============================================================================
-- Metadatos de archivos adjuntos

CREATE TABLE IF NOT EXISTS notification_attachments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    message_id VARCHAR(255) NOT NULL,
    
    -- Información del archivo
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    size_bytes INT UNSIGNED,
    
    -- Hash para verificación
    file_hash VARCHAR(64),
    
    -- Almacenamiento (futuro: S3, local, etc.)
    storage_type VARCHAR(20) DEFAULT 'base64',
    storage_path VARCHAR(500),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    KEY idx_message_id (message_id),
    KEY idx_filename (filename),
    
    FOREIGN KEY (message_id) REFERENCES notifications(message_id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: provider_stats
-- =============================================================================
-- Estadísticas agregadas por proveedor (para dashboards futuros)

CREATE TABLE IF NOT EXISTS provider_stats (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    provider VARCHAR(50) NOT NULL,
    
    -- Periodo de estadística
    stat_date DATE NOT NULL,
    stat_hour TINYINT UNSIGNED,
    
    -- Contadores
    total_sent INT UNSIGNED DEFAULT 0,
    total_failed INT UNSIGNED DEFAULT 0,
    total_rejected INT UNSIGNED DEFAULT 0,
    
    -- Métricas
    avg_processing_time_ms INT UNSIGNED,
    max_processing_time_ms INT UNSIGNED,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_provider_date_hour (provider, stat_date, stat_hour),
    KEY idx_stat_date (stat_date),
    KEY idx_provider (provider)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- VISTAS ÚTILES
-- =============================================================================

-- Vista de notificaciones con último log
CREATE OR REPLACE VIEW v_notifications_with_last_log AS
SELECT 
    n.*,
    l.event_type as last_event_type,
    l.event_status as last_event_status,
    l.event_message as last_event_message,
    l.timestamp as last_event_timestamp
FROM notifications n
LEFT JOIN notification_logs l ON (
    n.message_id = l.message_id 
    AND l.timestamp = (
        SELECT MAX(timestamp) 
        FROM notification_logs 
        WHERE message_id = n.message_id
    )
);

-- Vista de estadísticas diarias por proveedor
CREATE OR REPLACE VIEW v_daily_provider_stats AS
SELECT 
    provider,
    DATE(created_at) as date,
    COUNT(*) as total_notifications,
    SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent_count,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_count,
    ROUND(AVG(CASE WHEN status = 'sent' THEN 
        TIMESTAMPDIFF(SECOND, created_at, sent_at) ELSE NULL END), 2) as avg_delivery_time_seconds
FROM notifications 
WHERE created_at >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
GROUP BY provider, DATE(created_at)
ORDER BY date DESC, provider;

-- =============================================================================
-- DATOS INICIALES
-- =============================================================================

-- Insertar todos los providers configurados
INSERT IGNORE INTO provider_stats (provider, stat_date, total_sent, total_failed, total_rejected) 
VALUES 
-- Email providers
('mailpit', CURRENT_DATE, 0, 0, 0),
('smtp_primary', CURRENT_DATE, 0, 0, 0),
('smtp_secondary', CURRENT_DATE, 0, 0, 0),
('smtp_bulk', CURRENT_DATE, 0, 0, 0),
('smtp_test', CURRENT_DATE, 0, 0, 0),

-- API providers
('api_sendgrid', CURRENT_DATE, 0, 0, 0),
('api_ses', CURRENT_DATE, 0, 0, 0),
('api_mailgun', CURRENT_DATE, 0, 0, 0),
('api_generic', CURRENT_DATE, 0, 0, 0),

-- Twilio providers
('twilio_sms', CURRENT_DATE, 0, 0, 0),
('twilio_whatsapp', CURRENT_DATE, 0, 0, 0);

-- =============================================================================
-- COMENTARIOS PARA REFERENCIA
-- =============================================================================

/*
NOTAS DE USO:

1. REGENERAR NOTIFICACIÓN:
   SELECT params_json FROM notifications WHERE message_id = 'xxx';
   
2. AUDITORÍA COMPLETA:
   SELECT * FROM v_notifications_with_last_log WHERE message_id = 'xxx';
   
3. ESTADÍSTICAS DIARIAS:
   SELECT * FROM v_daily_provider_stats WHERE date >= '2024-01-01';
   
4. LOGS DE UN MENSAJE:
   SELECT * FROM notification_logs WHERE message_id = 'xxx' ORDER BY timestamp;

5. CLEANUP AUTOMÁTICO (ejecutar periódicamente):
   DELETE FROM notifications WHERE created_at < DATE_SUB(NOW(), INTERVAL 90 DAY);
*/