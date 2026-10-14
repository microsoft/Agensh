-- R9: gitea needs its own DB when GITEA_DB_TYPE=mysql (the large topologies).
--
-- sqlite3 stays the default and every historical sweep was measured on it, so
-- this file only CREATES the database -- it is inert unless gitea is pointed at
-- mysql. Created here rather than by gitea because the schema init runs as the
-- unprivileged 'omcgitea' user, which cannot CREATE DATABASE itself.
--
-- utf8mb4/general_ci matches gitea's own requirement: it refuses to start on a
-- database whose charset cannot hold 4-byte characters, and the failure is a
-- startup loop rather than a clear message.
CREATE DATABASE IF NOT EXISTS gitea CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
GRANT ALL PRIVILEGES ON gitea.* TO 'omcgitea'@'%';
FLUSH PRIVILEGES;
