-- =============================================================================
-- Database/init/04_provider_health_table.sql
-- NOTIFY-STACK - Tablas de health checks y monitoreo de proveedores
-- =============================================================================
-- Sistema de monitoreo y health checks para proveedores
-- Permite tracking de disponibilidad y performance

-- =============================================================================
-- CONFIGURACIÓN INICIAL
-- =============================================================================
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- =============================================================================
-- TABLA: provider_health_checks
-- =============================================================================
-- Historial detallado de health checks de proveedores

CREATE TABLE IF NOT EXISTS provider_health_checks (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Referencia al proveedor
    provider_id INT UNSIGNED NOT NULL,
    
    -- Resultado del health check
    is_healthy BOOLEAN NOT NULL,
    response_time_ms INT UNSIGNED,
    
    -- Detalles técnicos
    status_code INT,
    response_body TEXT,
    error_message TEXT,
    error_details JSON,
    
    -- Metadata del check
    check_type ENUM('manual', 'automatic', 'startup', 'scheduled', 'on_demand') DEFAULT 'automatic',
    check_endpoint VARCHAR(500),
    check_method ENUM('GET', 'POST', 'HEAD', 'SMTP', 'API') DEFAULT 'GET',
    
    -- Contexto del check
    checked_by VARCHAR(100),
    check_source VARCHAR(50), -- 'health_service', 'admin_panel', 'monitoring'
    request_id VARCHAR(255),
    
    -- Timestamp
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    KEY idx_provider_checked (provider_id, checked_at),
    KEY idx_healthy_status (is_healthy, checked_at),
    KEY idx_check_type (check_type),
    KEY idx_response_time (response_time_ms),
    
    FOREIGN KEY (provider_id) REFERENCES providers(id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: provider_health_config
-- =============================================================================
-- Configuración específica de health checks por proveedor

CREATE TABLE IF NOT EXISTS provider_health_config (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Referencia al proveedor
    provider_id INT UNSIGNED NOT NULL UNIQUE,
    
    -- Configuración del health check
    enabled BOOLEAN DEFAULT TRUE,
    check_interval_minutes INT UNSIGNED DEFAULT 5,
    timeout_seconds INT UNSIGNED DEFAULT 30,
    
    -- Endpoint y método de verificación
    health_check_url VARCHAR(500),
    check_method ENUM('GET', 'POST', 'HEAD', 'SMTP', 'API') DEFAULT 'GET',
    expected_status_code INT DEFAULT 200,
    expected_response_pattern VARCHAR(500),
    
    -- Headers y auth para el check (JSON)
    check_headers JSON,
    check_auth JSON,
    
    -- Criterios de salud
    consecutive_failures_threshold INT UNSIGNED DEFAULT 3,
    consecutive_successes_threshold INT UNSIGNED DEFAULT 2,
    max_response_time_ms INT UNSIGNED DEFAULT 5000,
    
    -- Configuración de alertas
    alert_on_failure BOOLEAN DEFAULT TRUE,
    alert_on_recovery BOOLEAN DEFAULT TRUE,
    alert_recipients JSON,
    
    -- Metadatos
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_provider_health_config (provider_id),
    KEY idx_enabled (enabled),
    KEY idx_check_interval (check_interval_minutes),
    
    FOREIGN KEY (provider_id) REFERENCES providers(id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: provider_health_incidents
-- =============================================================================
-- Registro de incidentes y problemas de proveedores

CREATE TABLE IF NOT EXISTS provider_health_incidents (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Referencia al proveedor
    provider_id INT UNSIGNED NOT NULL,
    
    -- Información del incidente
    incident_key VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- Estado del incidente
    status ENUM('open', 'investigating', 'resolved', 'closed') DEFAULT 'open',
    severity ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
    
    -- Impacto
    impact_description TEXT,
    affected_operations JSON,
    estimated_downtime_minutes INT UNSIGNED,
    
    -- Resolución
    resolution_notes TEXT,
    root_cause TEXT,
    preventive_actions TEXT,
    
    -- Timestamps de ciclo de vida
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP NULL,
    resolved_at TIMESTAMP NULL,
    closed_at TIMESTAMP NULL,
    
    -- Responsables
    assigned_to VARCHAR(100),
    resolved_by VARCHAR(100),
    
    -- Metadatos
    created_by VARCHAR(100),
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_provider_incident (provider_id, incident_key),
    KEY idx_status (status),
    KEY idx_severity (severity),
    KEY idx_detected_at (detected_at),
    KEY idx_provider_status (provider_id, status),
    
    FOREIGN KEY (provider_id) REFERENCES providers(id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: provider_health_metrics
-- =============================================================================
-- Métricas agregadas de salud por proveedor y período

CREATE TABLE IF NOT EXISTS provider_health_metrics (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Referencia al proveedor
    provider_id INT UNSIGNED NOT NULL,
    
    -- Período de la métrica
    metric_date DATE NOT NULL,
    metric_hour TINYINT UNSIGNED,
    
    -- Contadores de health checks
    total_checks INT UNSIGNED DEFAULT 0,
    successful_checks INT UNSIGNED DEFAULT 0,
    failed_checks INT UNSIGNED DEFAULT 0,
    
    -- Métricas de performance
    avg_response_time_ms INT UNSIGNED,
    min_response_time_ms INT UNSIGNED,
    max_response_time_ms INT UNSIGNED,
    p95_response_time_ms INT UNSIGNED,
    
    -- Métricas de disponibilidad
    uptime_percentage DECIMAL(5,2),
    downtime_minutes INT UNSIGNED DEFAULT 0,
    
    -- Errores y incidentes
    error_count INT UNSIGNED DEFAULT 0,
    incident_count INT UNSIGNED DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_provider_date_hour (provider_id, metric_date, metric_hour),
    KEY idx_metric_date (metric_date),
    KEY idx_provider_date (provider_id, metric_date),
    KEY idx_uptime_percentage (uptime_percentage),
    
    FOREIGN KEY (provider_id) REFERENCES providers(id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- VISTAS ÚTILES
-- =============================================================================

-- Vista de estado actual de proveedores
CREATE OR REPLACE VIEW v_provider_health_status AS
SELECT 
    p.provider_key,
    p.name,
    p.provider_type,
    p.enabled,
    p.is_healthy,
    p.last_health_check,
    hc.is_healthy as last_check_result,
    hc.response_time_ms as last_response_time,
    hc.checked_at as last_check_time,
    hc.error_message as last_error,
    cfg.check_interval_minutes,
    cfg.enabled as health_check_enabled,
    -- Calcular tiempo desde último check
    TIMESTAMPDIFF(MINUTE, hc.checked_at, NOW()) as minutes_since_last_check,
    -- Estado general
    CASE 
        WHEN p.enabled = FALSE THEN 'disabled'
        WHEN cfg.enabled = FALSE THEN 'monitoring_disabled'
        WHEN hc.checked_at IS NULL THEN 'never_checked'
        WHEN TIMESTAMPDIFF(MINUTE, hc.checked_at, NOW()) > cfg.check_interval_minutes * 2 THEN 'stale'
        WHEN hc.is_healthy = TRUE THEN 'healthy'
        ELSE 'unhealthy'
    END as overall_status
FROM providers p
LEFT JOIN provider_health_config cfg ON p.id = cfg.provider_id
LEFT JOIN provider_health_checks hc ON (
    p.id = hc.provider_id 
    AND hc.checked_at = (
        SELECT MAX(checked_at) 
        FROM provider_health_checks 
        WHERE provider_id = p.id
    )
);

-- Vista de métricas recientes por proveedor
CREATE OR REPLACE VIEW v_provider_recent_metrics AS
SELECT 
    p.provider_key,
    p.name,
    m.metric_date,
    m.uptime_percentage,
    m.avg_response_time_ms,
    m.total_checks,
    m.successful_checks,
    m.failed_checks,
    m.error_count,
    m.incident_count,
    ROUND((m.successful_checks * 100.0 / NULLIF(m.total_checks, 0)), 2) as success_rate_percentage
FROM providers p
JOIN provider_health_metrics m ON p.id = m.provider_id
WHERE m.metric_date >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAYS)
ORDER BY p.provider_key, m.metric_date DESC;

-- Vista de incidentes activos
CREATE OR REPLACE VIEW v_active_health_incidents AS
SELECT 
    p.provider_key,
    p.name as provider_name,
    i.incident_key,
    i.title,
    i.status,
    i.severity,
    i.detected_at,
    i.assigned_to,
    TIMESTAMPDIFF(HOUR, i.detected_at, NOW()) as hours_open,
    i.impact_description
FROM providers p
JOIN provider_health_incidents i ON p.id = i.provider_id
WHERE i.status IN ('open', 'investigating')
ORDER BY i.severity DESC, i.detected_at ASC;

-- =============================================================================
-- DATOS INICIALES - CONFIGURACIÓN BÁSICA
-- =============================================================================

-- Configurar health checks para proveedores básicos
-- (Se ejecutará después de que existan los providers)

-- =============================================================================
-- TRIGGERS PARA MANTENIMIENTO AUTOMÁTICO
-- =============================================================================

-- Trigger para actualizar timestamp de último health check en providers
DELIMITER $$

CREATE TRIGGER tr_update_provider_last_health_check
AFTER INSERT ON provider_health_checks
FOR EACH ROW
BEGIN
    UPDATE providers 
    SET 
        is_healthy = NEW.is_healthy,
        last_health_check = NEW.checked_at,
        last_error_message = CASE 
            WHEN NEW.is_healthy = FALSE THEN NEW.error_message 
            ELSE NULL 
        END
    WHERE id = NEW.provider_id;
END$$

DELIMITER ;

-- =============================================================================
-- COMENTARIOS PARA REFERENCIA
-- =============================================================================

/*
EJEMPLOS DE USO:

1. VER ESTADO ACTUAL DE TODOS LOS PROVEEDORES:
   SELECT * FROM v_provider_health_status;

2. INSERTAR HEALTH CHECK MANUAL:
   INSERT INTO provider_health_checks (provider_id, is_healthy, check_type, checked_by) 
   VALUES (1, TRUE, 'manual', 'admin');

3. CONFIGURAR HEALTH CHECK AUTOMÁTICO:
   INSERT INTO provider_health_config (provider_id, enabled, check_interval_minutes, health_check_url) 
   VALUES (1, TRUE, 5, 'https://api.provider.com/health');

4. CREAR INCIDENTE:
   INSERT INTO provider_health_incidents (provider_id, incident_key, title, severity, status) 
   VALUES (1, 'INC-2024-001', 'SMTP Connection Timeout', 'high', 'open');

5. VER MÉTRICAS DE LA ÚLTIMA SEMANA:
   SELECT * FROM v_provider_recent_metrics WHERE provider_key = 'smtp_primary';

6. LISTAR INCIDENTES ACTIVOS:
   SELECT * FROM v_active_health_incidents;

7. OBTENER PROVEEDORES SALUDABLES:
   SELECT provider_key FROM v_provider_health_status 
   WHERE overall_status = 'healthy' AND enabled = TRUE;

8. ESTADÍSTICAS DE UPTIME:
   SELECT provider_key, 
          AVG(uptime_percentage) as avg_uptime,
          MIN(uptime_percentage) as min_uptime
   FROM v_provider_recent_metrics 
   GROUP BY provider_key;
*/