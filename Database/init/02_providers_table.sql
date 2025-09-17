-- =============================================================================
-- Database/init/02_providers_table.sql
-- NOTIFY-STACK - Tabla de proveedores de notificaciones
-- =============================================================================
-- Migración de providers.yml hacia base de datos MySQL
-- Permite gestión dinámica de proveedores sin redeploy

-- =============================================================================
-- CONFIGURACIÓN INICIAL
-- =============================================================================
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- =============================================================================
-- TABLA: providers
-- =============================================================================
-- Configuración principal de proveedores de notificación

CREATE TABLE IF NOT EXISTS providers (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Identificador único del proveedor
    provider_key VARCHAR(50) NOT NULL UNIQUE,
    
    -- Información básica
    name VARCHAR(100) NOT NULL,
    description TEXT,
    provider_type ENUM('smtp', 'api', 'webhook', 'twilio') NOT NULL,
    
    -- Estado y configuración
    enabled BOOLEAN DEFAULT TRUE,
    priority INT UNSIGNED DEFAULT 100,
    weight INT UNSIGNED DEFAULT 10,
    
    -- Límites y configuración
    max_retries INT UNSIGNED DEFAULT 3,
    timeout_seconds INT UNSIGNED DEFAULT 30,
    rate_limit_per_minute INT UNSIGNED DEFAULT 60,
    
    -- Configuración específica del proveedor (JSON)
    config_json JSON NOT NULL,
    
    -- Credenciales cifradas (JSON)
    credentials_json JSON,
    
    -- Configuración de salud y monitoreo
    health_check_enabled BOOLEAN DEFAULT TRUE,
    health_check_url VARCHAR(500),
    health_check_interval_minutes INT UNSIGNED DEFAULT 5,
    
    -- Estados de operación
    is_healthy BOOLEAN DEFAULT TRUE,
    last_health_check TIMESTAMP NULL,
    last_error_message TEXT,
    
    -- Metadatos de gestión
    environment ENUM('development', 'staging', 'production') DEFAULT 'production',
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_provider_key (provider_key),
    KEY idx_provider_type (provider_type),
    KEY idx_enabled_priority (enabled, priority),
    KEY idx_environment (environment),
    KEY idx_health_status (is_healthy, enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: provider_groups
-- =============================================================================
-- Agrupación de proveedores para routing y balanceo

CREATE TABLE IF NOT EXISTS provider_groups (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Identificador del grupo
    group_key VARCHAR(50) NOT NULL UNIQUE,
    
    -- Información básica
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Configuración de routing
    routing_strategy ENUM('priority', 'round_robin', 'failover', 'load_balance') DEFAULT 'priority',
    fallback_enabled BOOLEAN DEFAULT TRUE,
    
    -- Estado
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Metadatos
    environment ENUM('development', 'staging', 'production') DEFAULT 'production',
    created_by VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_group_key (group_key),
    KEY idx_enabled (enabled),
    KEY idx_environment (environment)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: provider_group_members
-- =============================================================================
-- Relación N:N entre grupos y proveedores

CREATE TABLE IF NOT EXISTS provider_group_members (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Referencias
    group_id INT UNSIGNED NOT NULL,
    provider_id INT UNSIGNED NOT NULL,
    
    -- Configuración en el grupo
    priority INT UNSIGNED DEFAULT 100,
    weight INT UNSIGNED DEFAULT 10,
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_group_provider (group_id, provider_id),
    KEY idx_group_enabled_priority (group_id, enabled, priority),
    
    FOREIGN KEY (group_id) REFERENCES provider_groups(id) 
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES providers(id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: provider_health_checks
-- =============================================================================
-- Historial de health checks de proveedores

CREATE TABLE IF NOT EXISTS provider_health_checks (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Referencia al proveedor
    provider_id INT UNSIGNED NOT NULL,
    
    -- Resultado del check
    is_healthy BOOLEAN NOT NULL,
    response_time_ms INT UNSIGNED,
    
    -- Detalles
    status_code INT,
    error_message TEXT,
    response_body TEXT,
    
    -- Metadata
    check_type ENUM('manual', 'automatic', 'startup') DEFAULT 'automatic',
    checked_by VARCHAR(100),
    
    -- Timestamp
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    KEY idx_provider_checked (provider_id, checked_at),
    KEY idx_healthy_status (is_healthy, checked_at),
    
    FOREIGN KEY (provider_id) REFERENCES providers(id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- VISTAS ÚTILES
-- =============================================================================

-- Vista de proveedores activos con última verificación
CREATE OR REPLACE VIEW v_active_providers AS
SELECT 
    p.*,
    hc.checked_at as last_health_check_time,
    hc.response_time_ms as last_response_time_ms,
    hc.error_message as last_health_error
FROM providers p
LEFT JOIN provider_health_checks hc ON (
    p.id = hc.provider_id 
    AND hc.checked_at = (
        SELECT MAX(checked_at) 
        FROM provider_health_checks 
        WHERE provider_id = p.id
    )
)
WHERE p.enabled = TRUE;

-- Vista de grupos con conteo de proveedores
CREATE OR REPLACE VIEW v_provider_groups_summary AS
SELECT 
    pg.*,
    COUNT(pgm.provider_id) as total_providers,
    SUM(CASE WHEN pgm.enabled = TRUE THEN 1 ELSE 0 END) as enabled_providers
FROM provider_groups pg
LEFT JOIN provider_group_members pgm ON pg.id = pgm.group_id
GROUP BY pg.id, pg.group_key, pg.name, pg.description, 
         pg.routing_strategy, pg.fallback_enabled, pg.enabled, 
         pg.environment, pg.created_by, pg.created_at, pg.updated_at;

-- =============================================================================
-- DATOS INICIALES - PROVIDERS BÁSICOS
-- =============================================================================

-- Insertar proveedores básicos desde la configuración YAML actual
INSERT IGNORE INTO providers (provider_key, name, provider_type, config_json, credentials_json, description) VALUES

-- Email SMTP providers
('mailpit', 'Mailpit Development', 'smtp', 
 JSON_OBJECT('host', 'mailpit', 'port', 1025, 'use_tls', false, 'use_ssl', false),
 JSON_OBJECT('username', '', 'password', ''),
 'Servidor SMTP de desarrollo para testing'
),

('smtp_primary', 'SMTP Primary', 'smtp',
 JSON_OBJECT('host', '${SMTP_HOST_PRIMARY}', 'port', 587, 'use_tls', true, 'use_ssl', false),
 JSON_OBJECT('username', '${SMTP_USER_PRIMARY}', 'password', '${SMTP_PASS_PRIMARY}'),
 'Servidor SMTP principal de producción'
),

-- API providers
('api_sendgrid', 'SendGrid API', 'api',
 JSON_OBJECT('api_url', 'https://api.sendgrid.com/v3/mail/send', 'timeout', 30),
 JSON_OBJECT('api_key', '${SENDGRID_API_KEY}'),
 'SendGrid API para envío masivo'
);

-- =============================================================================
-- DATOS INICIALES - GRUPOS BÁSICOS  
-- =============================================================================

INSERT IGNORE INTO provider_groups (group_key, name, routing_strategy, description) VALUES
('default_email', 'Default Email Group', 'priority', 'Grupo por defecto para notificaciones email'),
('high_priority', 'High Priority Group', 'failover', 'Grupo para notificaciones críticas'),
('bulk_email', 'Bulk Email Group', 'load_balance', 'Grupo para envío masivo');

-- =============================================================================
-- COMENTARIOS PARA REFERENCIA
-- =============================================================================

/*
EJEMPLOS DE USO:

1. LISTAR PROVEEDORES ACTIVOS:
   SELECT * FROM v_active_providers;

2. OBTENER CONFIGURACIÓN DE PROVEEDOR:
   SELECT config_json FROM providers WHERE provider_key = 'mailpit';

3. HEALTH CHECK MANUAL:
   INSERT INTO provider_health_checks (provider_id, is_healthy, check_type, checked_by) 
   VALUES (1, TRUE, 'manual', 'admin');

4. DESHABILITAR PROVEEDOR:
   UPDATE providers SET enabled = FALSE WHERE provider_key = 'smtp_primary';

5. ESTADÍSTICAS DE SALUD:
   SELECT provider_key, 
          AVG(response_time_ms) as avg_response, 
          COUNT(*) as check_count
   FROM providers p 
   JOIN provider_health_checks hc ON p.id = hc.provider_id 
   WHERE hc.checked_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
   GROUP BY provider_key;
*/