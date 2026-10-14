-- R8: Mattermost needs its own DB (uses the existing 'omcgitea' user).
CREATE DATABASE IF NOT EXISTS mattermost CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
GRANT ALL PRIVILEGES ON mattermost.* TO 'omcgitea'@'%';
FLUSH PRIVILEGES;
