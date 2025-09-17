-- =============================================================================
-- Database/init/03_provider_groups_table.sql
-- NOTIFY-STACK - Tablas de grupos de proveedores
-- =============================================================================
-- Complemento a providers table para agrupación y balanceo de carga
-- Permite routing avanzado y failover entre proveedores

-- =============================================================================
-- CONFIGURACIÓN INICIAL
-- =============================================================================
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- =============================================================================
-- TABLA: provider_groups
-- =============================================================================
-- Agrupación lógica de proveedores para routing y balanceo

CREATE TABLE IF NOT EXISTS provider_groups (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Identificador único del grupo
    group_key VARCHAR(50) NOT NULL UNIQUE,
    
    -- Información básica
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Estrategia de routing dentro del grupo
    routing_strategy ENUM('priority', 'round_robin', 'failover', 'load_balance', 'random') DEFAULT 'priority',
    
    -- Configuración de failover
    failover_enabled BOOLEAN DEFAULT TRUE,
    failover_timeout_seconds INT UNSIGNED DEFAULT 30,
    
    -- Configuración de retry
    max_group_retries INT UNSIGNED DEFAULT 2,
    retry_delay_seconds INT UNSIGNED DEFAULT 5,
    
    -- Estado del grupo
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Metadatos de gestión
    environment ENUM('development', 'staging', 'production') DEFAULT 'production',
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_group_key (group_key),
    KEY idx_enabled (enabled),
    KEY idx_environment (environment),
    KEY idx_routing_strategy (routing_strategy)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: provider_group_members
-- =============================================================================
-- Relación N:N entre grupos y proveedores con configuración específica

CREATE TABLE IF NOT EXISTS provider_group_members (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Referencias a grupo y proveedor
    group_id INT UNSIGNED NOT NULL,
    provider_id INT UNSIGNED NOT NULL,
    
    -- Configuración dentro del grupo
    priority INT UNSIGNED DEFAULT 100,
    weight INT UNSIGNED DEFAULT 10,
    
    -- Estado específico en el grupo
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Configuración de failover específica del miembro
    max_member_retries INT UNSIGNED DEFAULT 3,
    timeout_override_seconds INT UNSIGNED NULL,
    
    -- Configuración de load balancing
    capacity_limit INT UNSIGNED NULL,
    current_load INT UNSIGNED DEFAULT 0,
    
    -- Metadatos
    added_by VARCHAR(100),
    notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_group_provider (group_id, provider_id),
    KEY idx_group_enabled_priority (group_id, enabled, priority),
    KEY idx_group_weight (group_id, weight),
    KEY idx_provider_groups (provider_id),
    
    -- Referencias foráneas a tablas existentes
    FOREIGN KEY (group_id) REFERENCES provider_groups(id) 
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES providers(id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- TABLA: provider_group_routing
-- =============================================================================
-- Configuración de routing hacia grupos de proveedores

CREATE TABLE IF NOT EXISTS provider_group_routing (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    
    -- Identificador de la regla de routing
    route_key VARCHAR(50) NOT NULL UNIQUE,
    
    -- Información básica
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Target del routing
    target_group_id INT UNSIGNED NOT NULL,
    fallback_group_id INT UNSIGNED NULL,
    
    -- Condiciones de activación (JSON)
    conditions_json JSON,
    
    -- Configuración de la regla
    priority INT UNSIGNED DEFAULT 100,
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Metadatos
    environment ENUM('development', 'staging', 'production') DEFAULT 'production',
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (id),
    UNIQUE KEY uk_route_key (route_key),
    KEY idx_priority_enabled (priority, enabled),
    KEY idx_target_group (target_group_id),
    KEY idx_environment (environment),
    
    FOREIGN KEY (target_group_id) REFERENCES provider_groups(id) 
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (fallback_group_id) REFERENCES provider_groups(id) 
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- VISTAS ÚTILES
-- =============================================================================

-- Vista de grupos con conteo de proveedores
CREATE OR REPLACE VIEW v_provider_groups_summary AS
SELECT 
    pg.id,
    pg.group_key,
    pg.name,
    pg.description,
    pg.routing_strategy,
    pg.enabled,
    pg.environment,
    COUNT(pgm.provider_id) as total_providers,
    SUM(CASE WHEN pgm.enabled = TRUE THEN 1 ELSE 0 END) as active_providers,
    SUM(CASE WHEN p.enabled = TRUE AND p.is_healthy = TRUE AND pgm.enabled = TRUE THEN 1 ELSE 0 END) as healthy_providers,
    pg.created_at,
    pg.updated_at
FROM provider_groups pg
LEFT JOIN provider_group_members pgm ON pg.id = pgm.group_id
LEFT JOIN providers p ON pgm.provider_id = p.id
GROUP BY pg.id, pg.group_key, pg.name, pg.description, pg.routing_strategy, 
         pg.enabled, pg.environment, pg.created_at, pg.updated_at;

-- Vista de miembros de grupo con detalles del proveedor
CREATE OR REPLACE VIEW v_group_members_detailed AS
SELECT 
    pg.group_key,
    pg.name as group_name,
    pg.routing_strategy,
    p.provider_key,
    p.name as provider_name,
    p.provider_type,
    p.enabled as provider_enabled,
    p.is_healthy as provider_healthy,
    pgm.priority,
    pgm.weight,
    pgm.enabled as member_enabled,
    pgm.max_member_retries,
    pgm.timeout_override_seconds,
    pgm.capacity_limit,
    pgm.current_load,
    pgm.created_at as member_added_at
FROM provider_groups pg
JOIN provider_group_members pgm ON pg.id = pgm.group_id  
JOIN providers p ON pgm.provider_id = p.id
ORDER BY pg.group_key, pgm.priority ASC, pgm.weight DESC;

-- Vista de routing activo
CREATE OR REPLACE VIEW v_active_group_routing AS
SELECT 
    pgr.route_key,
    pgr.name,
    pgr.description,
    pgr.priority,
    tg.group_key as target_group,
    tg.name as target_group_name,
    fg.group_key as fallback_group,
    fg.name as fallback_group_name,
    pgr.conditions_json,
    pgr.environment,
    pgr.created_at
FROM provider_group_routing pgr
JOIN provider_groups tg ON pgr.target_group_id = tg.id
LEFT JOIN provider_groups fg ON pgr.fallback_group_id = fg.id
WHERE pgr.enabled = TRUE
ORDER BY pgr.priority ASC;

-- =============================================================================
-- DATOS INICIALES - GRUPOS BÁSICOS
-- =============================================================================

-- Insertar grupos básicos de proveedores
INSERT IGNORE INTO provider_groups (group_key, name, routing_strategy, description) VALUES
('default_email', 'Default Email Group', 'priority', 'Grupo por defecto para notificaciones email'),
('high_priority', 'High Priority Group', 'failover', 'Grupo para notificaciones críticas con failover'),
('bulk_email', 'Bulk Email Group', 'load_balance', 'Grupo para envío masivo con balance de carga'),
('development', 'Development Group', 'round_robin', 'Grupo para ambiente de desarrollo'),
('api_providers', 'API Providers Group', 'priority', 'Proveedores que usan API (SendGrid, SES, etc.)'),
('smtp_providers', 'SMTP Providers Group', 'failover', 'Proveedores SMTP tradicionales');

-- =============================================================================
-- DATOS INICIALES - ROUTING BÁSICO
-- =============================================================================

-- Insertar reglas básicas de routing a grupos
INSERT IGNORE INTO provider_group_routing (route_key, name, target_group_id, conditions_json, priority, description) VALUES
('bulk_volume', 'Bulk Volume Routing', 
 (SELECT id FROM provider_groups WHERE group_key = 'bulk_email'), 
 JSON_OBJECT('recipient_count', '>=', 'value', 50), 
 10, 'Envíos masivos (50+ destinatarios) al grupo bulk'),

('high_priority_templates', 'High Priority Templates', 
 (SELECT id FROM provider_groups WHERE group_key = 'high_priority'), 
 JSON_OBJECT('template_pattern', '^', 'value', 'critical-|urgent-|alert-'), 
 20, 'Templates críticos al grupo high priority'),

('dev_environment', 'Development Environment', 
 (SELECT id FROM provider_groups WHERE group_key = 'development'), 
 JSON_OBJECT('environment', '==', 'value', 'development'), 
 5, 'Todas las notificaciones en desarrollo');

-- =============================================================================
-- COMENTARIOS PARA REFERENCIA
-- =============================================================================

/*
EJEMPLOS DE USO:

1. LISTAR GRUPOS CON ESTADÍSTICAS:
   SELECT * FROM v_provider_groups_summary;

2. VER MIEMBROS DE UN GRUPO:
   SELECT * FROM v_group_members_detailed WHERE group_key = 'high_priority';

3. AGREGAR PROVEEDOR A GRUPO:
   INSERT INTO provider_group_members (group_id, provider_id, priority, weight) 
   VALUES ((SELECT id FROM provider_groups WHERE group_key = 'bulk_email'),
           (SELECT id FROM providers WHERE provider_key = 'smtp_bulk'), 10, 20);

4. HABILITAR/DESHABILITAR GRUPO:
   UPDATE provider_groups SET enabled = FALSE WHERE group_key = 'maintenance_group';

5. CAMBIAR ESTRATEGIA DE ROUTING:
   UPDATE provider_groups SET routing_strategy = 'load_balance' WHERE group_key = 'api_providers';

6. VER ROUTING ACTIVO:
   SELECT * FROM v_active_group_routing;

7. OBTENER PROVEEDORES ACTIVOS DE UN GRUPO (ordenados por prioridad):
   SELECT provider_key, priority, weight 
   FROM v_group_members_detailed 
   WHERE group_key = 'high_priority' 
     AND provider_enabled = TRUE 
     AND provider_healthy = TRUE 
     AND member_enabled = TRUE
   ORDER BY priority ASC, weight DESC;
*/