-- =============================================================================
-- Database/init/00_create_user.sql
-- NOTIFY-STACK - Usuario y permisos MySQL
-- =============================================================================
-- Se ejecuta ANTES del script de tablas para garantizar permisos correctos

-- Crear usuario para conexiones desde cualquier IP del contenedor
CREATE USER IF NOT EXISTS 'notify_user'@'%' IDENTIFIED BY 'notify_password_secure_2024';

-- Otorgar todos los permisos en la base de datos notify_db
GRANT ALL PRIVILEGES ON notify_db.* TO 'notify_user'@'%';

-- Permitir conexión desde localhost también (para debugging)
CREATE USER IF NOT EXISTS 'notify_user'@'localhost' IDENTIFIED BY 'notify_password_secure_2024';
GRANT ALL PRIVILEGES ON notify_db.* TO 'notify_user'@'localhost';

-- Aplicar cambios
FLUSH PRIVILEGES;

-- Verificar que el usuario fue creado correctamente
SELECT user, host FROM mysql.user WHERE user = 'notify_user';