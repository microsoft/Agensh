-- Mattermost owns its tables in a separate database on the shared MySQL instance.
CREATE DATABASE IF NOT EXISTS mattermost CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
GRANT ALL PRIVILEGES ON mattermost.* TO 'omcgitea'@'%';
FLUSH PRIVILEGES;
