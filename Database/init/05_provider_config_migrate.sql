-- =============================================================================
-- Database/init/05_provider_config_migrate.sql
-- NOTIFY-STACK - Migración de datos providers.yml a base de datos
-- =============================================================================
-- Inserta todos los providers del YAML actual en las tablas de base de datos
-- Ejecutado automáticamente después de crear las tablas

-- =============================================================================
-- CONFIGURACIÓN INICIAL
-- =============================================================================
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- =============================================================================
-- PROVIDERS - DESARROLLO
-- =============================================================================

-- MailPit Development
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'mailpit', 
    'MailPit Development', 
    'Capturador de correos para desarrollo y testing',
    'smtp',
    TRUE, 
    10, 
    100, 
    1, 
    15, 
    1000,
    JSON_OBJECT(
        'host', 'mailpit',
        'port', 1025,
        'use_tls', false,
        'use_ssl', false,
        'verify_certificate', false,
        'from_email', 'dev@notify-system.local',
        'from_name', 'Notify Dev System',
        'reply_to', 'dev@notify-system.local',
        'return_path', 'dev@notify-system.local',
        'max_recipients_per_message', 100,
        'max_messages_per_hour', 1000,
        'max_attachment_size', 25165824,
        'category', 'development'
    ),
    JSON_OBJECT(
        'username', '',
        'password', ''
    ),
    FALSE,
    60,
    'development',
    'migration_script'
);

-- =============================================================================
-- PROVIDERS - SMTP PRODUCTION
-- =============================================================================

-- Gmail SMTP Primary
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'smtp_primary', 
    'Gmail SMTP Primary', 
    'Proveedor principal para emails transaccionales',
    'smtp',
    TRUE, 
    20, 
    70, 
    3, 
    30, 
    500,
    JSON_OBJECT(
        'host', '${SMTP_GMAIL_HOST}',
        'port', 587,
        'use_tls', true,
        'use_ssl', false,
        'verify_certificate', true,
        'from_name', '${SMTP_GMAIL_FROM_NAME}',
        'reply_to', '${SMTP_GMAIL_USERNAME}',
        'return_path', '${SMTP_GMAIL_USERNAME}',
        'max_recipients_per_message', 100,
        'max_messages_per_hour', 500,
        'max_attachment_size', 25165824,
        'category', 'transactional',
        'features', JSON_OBJECT(
            'html_support', true,
            'attachments', true,
            'tracking', false,
            'analytics', false,
            'templates', false
        )
    ),
    JSON_OBJECT(
        'username', '${SMTP_GMAIL_USERNAME}',
        'password', '${SMTP_GMAIL_PASSWORD}',
        'from_email', '${SMTP_GMAIL_USERNAME}'
    ),
    TRUE,
    5,
    'production',
    'migration_script'
);

-- Outlook SMTP Secondary
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'smtp_secondary', 
    'Outlook SMTP Secondary', 
    'Proveedor de respaldo para failover',
    'smtp',
    FALSE, 
    50, 
    50, 
    3, 
    30, 
    300,
    JSON_OBJECT(
        'host', '${SMTP_OUTLOOK_HOST}',
        'port', 587,
        'use_tls', true,
        'use_ssl', false,
        'from_name', 'Notify System Backup',
        'max_recipients_per_message', 50,
        'max_messages_per_hour', 300,
        'category', 'backup',
        'features', JSON_OBJECT(
            'html_support', true,
            'attachments', true,
            'tracking', false
        )
    ),
    JSON_OBJECT(
        'username', '${SMTP_OUTLOOK_USERNAME}',
        'password', '${SMTP_OUTLOOK_PASSWORD}',
        'from_email', '${SMTP_OUTLOOK_USERNAME}'
    ),
    TRUE,
    10,
    'production',
    'migration_script'
);

-- Custom SMTP Bulk
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'smtp_bulk', 
    'Custom SMTP Bulk', 
    'Proveedor optimizado para envíos masivos',
    'smtp',
    FALSE, 
    30, 
    60, 
    3, 
    45, 
    2000,
    JSON_OBJECT(
        'host', '${SMTP_CUSTOM_HOST}',
        'port', 587,
        'use_tls', true,
        'use_ssl', false,
        'from_name', 'Newsletter System',
        'max_recipients_per_message', 500,
        'max_messages_per_hour', 2000,
        'category', 'bulk',
        'features', JSON_OBJECT(
            'html_support', true,
            'attachments', false,
            'tracking', false
        )
    ),
    JSON_OBJECT(
        'username', '${SMTP_CUSTOM_USERNAME}',
        'password', '${SMTP_CUSTOM_PASSWORD}',
        'from_email', '${SMTP_CUSTOM_USERNAME}'
    ),
    TRUE,
    15,
    'production',
    'migration_script'
);

-- Test SMTP Provider
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'smtp_test', 
    'Test SMTP Provider', 
    'Proveedor exclusivo para testing y desarrollo',
    'smtp',
    FALSE, 
    100, 
    10, 
    3, 
    15, 
    100,
    JSON_OBJECT(
        'host', 'smtp.mailtrap.io',
        'port', 587,
        'use_tls', true,
        'use_ssl', false,
        'from_email', 'test@notify-system.local',
        'from_name', 'Notify Test System',
        'max_recipients_per_message', 10,
        'max_messages_per_hour', 100,
        'category', 'testing',
        'features', JSON_OBJECT(
            'html_support', true,
            'attachments', true,
            'tracking', true
        )
    ),
    JSON_OBJECT(
        'username', '${SMTP_TEST_USERNAME}',
        'password', '${SMTP_TEST_PASSWORD}'
    ),
    TRUE,
    30,
    'development',
    'migration_script'
);

-- =============================================================================
-- PROVIDERS - API SERVICES
-- =============================================================================

-- SendGrid API
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'api_sendgrid', 
    'SendGrid API', 
    'Proveedor API premium con tracking avanzado',
    'api',
    FALSE, 
    15, 
    30, 
    3, 
    30, 
    10000,
    JSON_OBJECT(
        'endpoint', 'https://api.sendgrid.com',
        'provider_type', 'sendgrid',
        'from_name', '${SENDGRID_FROM_NAME}',
        'reply_to', '${SENDGRID_FROM_EMAIL}',
        'max_recipients_per_message', 1000,
        'max_messages_per_hour', 10000,
        'max_attachment_size', 10485760,
        'category', 'premium',
        'features', JSON_OBJECT(
            'html_support', true,
            'attachments', true,
            'tracking', true,
            'analytics', true,
            'templates', true,
            'webhooks', true
        ),
        'sendgrid_config', JSON_OBJECT(
            'click_tracking', true,
            'open_tracking', true,
            'subscription_tracking', false,
            'template_engine', true,
            'dynamic_templates', true,
            'ip_pool_name', 'default'
        )
    ),
    JSON_OBJECT(
        'api_key', '${SENDGRID_API_KEY}',
        'from_email', '${SENDGRID_FROM_EMAIL}'
    ),
    TRUE,
    5,
    'production',
    'migration_script'
);

-- Amazon SES API
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'api_ses', 
    'Amazon SES', 
    'Proveedor AWS altamente escalable',
    'api',
    FALSE, 
    25, 
    50, 
    3, 
    30, 
    14000,
    JSON_OBJECT(
        'endpoint', 'https://email.${AWS_SES_REGION}.amazonaws.com',
        'provider_type', 'ses',
        'region', '${AWS_SES_REGION}',
        'from_name', 'AWS Notifications',
        'max_recipients_per_message', 50,
        'max_messages_per_hour', 14000,
        'category', 'scalable',
        'features', JSON_OBJECT(
            'html_support', true,
            'attachments', true,
            'tracking', true,
            'analytics', true,
            'templates', true
        ),
        'ses_config', JSON_OBJECT(
            'configuration_set', 'default'
        )
    ),
    JSON_OBJECT(
        'api_key', '${AWS_SES_ACCESS_KEY_ID}',
        'secret_key', '${AWS_SES_SECRET_ACCESS_KEY}',
        'from_email', '${AWS_SES_FROM_EMAIL}'
    ),
    TRUE,
    10,
    'production',
    'migration_script'
);

-- Mailgun API
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'api_mailgun', 
    'Mailgun API', 
    'Proveedor API con excelente deliverability',
    'api',
    FALSE, 
    30, 
    40, 
    3, 
    30, 
    5000,
    JSON_OBJECT(
        'endpoint', 'https://api.mailgun.net/v3/${MAILGUN_DOMAIN}',
        'provider_type', 'mailgun',
        'domain', '${MAILGUN_DOMAIN}',
        'from_name', 'Mailgun Notifications',
        'max_recipients_per_message', 1000,
        'max_messages_per_hour', 5000,
        'category', 'marketing',
        'features', JSON_OBJECT(
            'html_support', true,
            'attachments', true,
            'tracking', true,
            'analytics', true
        )
    ),
    JSON_OBJECT(
        'api_key', '${MAILGUN_API_KEY}',
        'from_email', '${MAILGUN_FROM_EMAIL}'
    ),
    TRUE,
    10,
    'production',
    'migration_script'
);

-- Generic API Provider
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'api_generic', 
    'Generic API Provider', 
    'Proveedor API genérico configurable',
    'api',
    FALSE, 
    100, 
    10, 
    2, 
    30, 
    1000,
    JSON_OBJECT(
        'endpoint', '${GENERIC_API_ENDPOINT}',
        'provider_type', 'generic',
        'from_name', 'Generic Provider',
        'max_recipients_per_message', 100,
        'max_messages_per_hour', 1000,
        'category', 'experimental',
        'headers', JSON_OBJECT(
            'User-Agent', 'NotifyAPI/1.0',
            'X-Custom-Header', 'notify-stack'
        ),
        'features', JSON_OBJECT(
            'html_support', true,
            'attachments', false
        )
    ),
    JSON_OBJECT(
        'api_key', '${GENERIC_API_KEY}',
        'from_email', '${GENERIC_FROM_EMAIL}'
    ),
    TRUE,
    30,
    'production',
    'migration_script'
);

-- =============================================================================
-- PROVIDERS - TWILIO SERVICES
-- =============================================================================

-- Twilio SMS
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'twilio_sms', 
    'Twilio SMS', 
    'Proveedor SMS via Twilio API',
    'twilio',
    FALSE, 
    10, 
    100, 
    2, 
    30, 
    100,
    JSON_OBJECT(
        'provider_type', 'twilio_sms',
        'max_recipients_per_message', 10,
        'max_message_length', 1600,
        'max_messages_per_hour', 100,
        'category', 'sms',
        'features', JSON_OBJECT(
            'html_support', false,
            'attachments', false,
            'tracking', true,
            'delivery_reports', true,
            'status_callbacks', true
        ),
        'sms_config', JSON_OBJECT(
            'webhook_url', '${TWILIO_SMS_WEBHOOK_URL}',
            'validity_period', 86400,
            'encoding', 'UTF-8',
            'smart_encoding', true
        ),
        'supported_media_types', JSON_ARRAY()
    ),
    JSON_OBJECT(
        'account_sid', '${TWILIO_ACCOUNT_SID}',
        'auth_token', '${TWILIO_AUTH_TOKEN}',
        'from_number', '${TWILIO_SMS_FROM}'
    ),
    TRUE,
    10,
    'production',
    'migration_script'
);

-- Twilio WhatsApp
INSERT IGNORE INTO providers (
    provider_key, name, description, provider_type, 
    enabled, priority, weight, max_retries, timeout_seconds, rate_limit_per_minute,
    config_json, credentials_json, 
    health_check_enabled, health_check_interval_minutes,
    environment, created_by
) VALUES (
    'twilio_whatsapp', 
    'Twilio WhatsApp', 
    'Proveedor WhatsApp Business via Twilio API',
    'twilio',
    FALSE, 
    10, 
    100, 
    2, 
    45, 
    50,
    JSON_OBJECT(
        'provider_type', 'twilio_whatsapp',
        'max_recipients_per_message', 5,
        'max_message_length', 4096,
        'max_media_count', 5,
        'max_media_size', 16777216,
        'max_messages_per_hour', 50,
        'category', 'whatsapp',
        'features', JSON_OBJECT(
            'html_support', false,
            'attachments', true,
            'media_support', true,
            'tracking', true,
            'delivery_reports', true,
            'read_receipts', true,
            'templates', true
        ),
        'whatsapp_config', JSON_OBJECT(
            'webhook_url', '${TWILIO_WHATSAPP_WEBHOOK_URL}',
            'use_templates', true,
            'fallback_language', 'en',
            'media_upload_timeout', 60
        ),
        'supported_media_types', JSON_ARRAY(
            'image/jpeg',
            'image/png',
            'application/pdf',
            'text/plain'
        )
    ),
    JSON_OBJECT(
        'account_sid', '${TWILIO_ACCOUNT_SID}',
        'auth_token', '${TWILIO_AUTH_TOKEN}',
        'from_number', '${TWILIO_WHATSAPP_FROM}'
    ),
    TRUE,
    15,
    'production',
    'migration_script'
);

-- =============================================================================
-- PROVIDER GROUPS
-- =============================================================================

-- Grupo Development
INSERT IGNORE INTO provider_groups (
    group_key, name, description, routing_strategy, 
    failover_enabled, max_group_retries, enabled,
    environment, created_by
) VALUES (
    'development', 
    'Development Group', 
    'Grupo principal para desarrollo',
    'priority',
    FALSE,
    0,
    TRUE,
    'development',
    'migration_script'
);

-- Grupo Transactional
INSERT IGNORE INTO provider_groups (
    group_key, name, description, routing_strategy, 
    failover_enabled, max_group_retries, enabled,
    environment, created_by
) VALUES (
    'transactional', 
    'Transactional Email Group', 
    'Grupo para emails transaccionales',
    'load_balance',
    TRUE,
    2,
    TRUE,
    'production',
    'migration_script'
);

-- Grupo Bulk
INSERT IGNORE INTO provider_groups (
    group_key, name, description, routing_strategy, 
    failover_enabled, max_group_retries, enabled,
    environment, created_by
) VALUES (
    'bulk', 
    'Bulk Email Group', 
    'Grupo para envíos masivos',
    'round_robin',
    TRUE,
    2,
    TRUE,
    'production',
    'migration_script'
);

-- Grupo Backup
INSERT IGNORE INTO provider_groups (
    group_key, name, description, routing_strategy, 
    failover_enabled, max_group_retries, enabled,
    environment, created_by
) VALUES (
    'backup', 
    'Backup Providers Group', 
    'Grupo de proveedores de respaldo',
    'failover',
    TRUE,
    3,
    TRUE,
    'production',
    'migration_script'
);

-- Grupo SMS
INSERT IGNORE INTO provider_groups (
    group_key, name, description, routing_strategy, 
    failover_enabled, max_group_retries, enabled,
    environment, created_by
) VALUES (
    'sms', 
    'SMS Providers Group', 
    'Grupo para notificaciones SMS',
    'priority',
    TRUE,
    2,
    FALSE,
    'production',
    'migration_script'
);

-- Grupo WhatsApp
INSERT IGNORE INTO provider_groups (
    group_key, name, description, routing_strategy, 
    failover_enabled, max_group_retries, enabled,
    environment, created_by
) VALUES (
    'whatsapp', 
    'WhatsApp Providers Group', 
    'Grupo para notificaciones WhatsApp',
    'priority',
    TRUE,
    2,
    FALSE,
    'production',
    'migration_script'
);

-- =============================================================================
-- PROVIDER GROUP MEMBERS
-- =============================================================================

-- Development Group Members
INSERT IGNORE INTO provider_group_members (group_id, provider_id, priority, weight, enabled, added_by)
SELECT 
    pg.id, p.id, 10, 100, TRUE, 'migration_script'
FROM provider_groups pg, providers p 
WHERE pg.group_key = 'development' AND p.provider_key = 'mailpit';

-- Transactional Group Members
INSERT IGNORE INTO provider_group_members (group_id, provider_id, priority, weight, enabled, added_by)
SELECT 
    pg.id, p.id, 10, 70, TRUE, 'migration_script'
FROM provider_groups pg, providers p 
WHERE pg.group_key = 'transactional' AND p.provider_key = 'smtp_primary';

INSERT IGNORE INTO provider_group_members (group_id, provider_id, priority, weight, enabled, added_by)
SELECT 
    pg.id, p.id, 20, 30, TRUE, 'migration_script'
FROM provider_groups pg, providers p 
WHERE pg.group_key = 'transactional' AND p.provider_key = 'api_sendgrid';

-- Bulk Group Members
INSERT IGNORE INTO provider_group_members (group_id, provider_id, priority, weight, enabled, added_by)
SELECT 
    pg.id, p.id, 10, 60, TRUE, 'migration_script'
FROM provider_groups pg, providers p 
WHERE pg.group_key = 'bulk' AND p.provider_key = 'smtp_bulk';

INSERT IGNORE INTO provider_group_members (group_id, provider_id, priority, weight, enabled, added_by)
SELECT 
    pg.id, p.id, 20, 40, TRUE, 'migration_script'
FROM provider_groups pg, providers p 
WHERE pg.group_key = 'bulk' AND p.provider_key = 'api_mailgun';

-- Backup Group Members
INSERT IGNORE INTO provider_group_members (group_id, provider_id, priority, weight, enabled, added_by)
SELECT 
    pg.id, p.id, 10, 50, TRUE, 'migration_script'
FROM provider_groups pg, providers p 
WHERE pg.group_key = 'backup' AND p.provider_key = 'smtp_secondary';

INSERT IGNORE INTO provider_group_members (group_id, provider_id, priority, weight, enabled, added_by)
SELECT 
    pg.id, p.id, 20, 50, TRUE, 'migration_script'
FROM provider_groups pg, providers p 
WHERE pg.group_key = 'backup' AND p.provider_key = 'api_ses';

-- SMS Group Members
INSERT IGNORE INTO provider_group_members (group_id, provider_id, priority, weight, enabled, added_by)
SELECT 
    pg.id, p.id, 10, 100, TRUE, 'migration_script'
FROM provider_groups pg, providers p 
WHERE pg.group_key = 'sms' AND p.provider_key = 'twilio_sms';

-- WhatsApp Group Members
INSERT IGNORE INTO provider_group_members (group_id, provider_id, priority, weight, enabled, added_by)
SELECT 
    pg.id, p.id, 10, 100, TRUE, 'migration_script'
FROM provider_groups pg, providers p 
WHERE pg.group_key = 'whatsapp' AND p.provider_key = 'twilio_whatsapp';

-- =============================================================================
-- HEALTH CHECK CONFIGURATIONS
-- =============================================================================

-- Configurar health checks para providers principales
INSERT IGNORE INTO provider_health_config (
    provider_id, enabled, check_interval_minutes, timeout_seconds,
    consecutive_failures_threshold, consecutive_successes_threshold,
    max_response_time_ms, alert_on_failure, alert_on_recovery,
    created_by
)
SELECT 
    p.id, TRUE, 5, 30, 3, 2, 5000, TRUE, TRUE, 'migration_script'
FROM providers p 
WHERE p.provider_key IN ('smtp_primary', 'api_sendgrid', 'api_mailgun', 'api_ses');

-- Health checks más frecuentes para servicios críticos
INSERT IGNORE INTO provider_health_config (
    provider_id, enabled, check_interval_minutes, timeout_seconds,
    consecutive_failures_threshold, consecutive_successes_threshold,
    max_response_time_ms, alert_on_failure, alert_on_recovery,
    created_by
)
SELECT 
    p.id, TRUE, 10, 45, 2, 2, 10000, TRUE, TRUE, 'migration_script'
FROM providers p 
WHERE p.provider_key IN ('twilio_sms', 'twilio_whatsapp');

-- =============================================================================
-- COMENTARIOS FINALES
-- =============================================================================

/*
DATOS MIGRADOS DESDE providers.yml:

✅ PROVIDERS MIGRADOS:
- mailpit (desarrollo)
- smtp_primary (Gmail)
- smtp_secondary (Outlook) 
- smtp_bulk (Custom)
- smtp_test (Mailtrap)
- api_sendgrid
- api_ses (Amazon)
- api_mailgun
- api_generic
- twilio_sms
- twilio_whatsapp

✅ GRUPOS MIGRADOS:
- development (mailpit)
- transactional (smtp_primary + api_sendgrid)
- bulk (smtp_bulk + api_mailgun)
- backup (smtp_secondary + api_ses)
- sms (twilio_sms)
- whatsapp (twilio_whatsapp)

✅ CONFIGURACIÓN ADICIONAL:
- Health check configs para providers principales
- Memberships con pesos del YAML original
- Variables de entorno preservadas
- Estados enabled/disabled del YAML

PRÓXIMOS PASOS:
1. Crear flag USE_DATABASE_PROVIDERS en constants.py
2. Modificar config_loader.py para modo dual
3. Actualizar routing_engine.py para usar DB
4. Crear endpoints administrativos
5. Testing completo antes de deprecar YAML
*/