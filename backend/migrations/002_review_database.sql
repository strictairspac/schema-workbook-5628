-- 复核库使用独立数据库（物理隔离）：源库回滚、误删不会波及复核副本。
-- 由 MySQL 首次初始化数据卷时执行；表结构由 ReviewBase.metadata.create_all 幂等创建。
CREATE DATABASE IF NOT EXISTS `schemaworkbook_review`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON `schemaworkbook_review`.* TO 'schemaworkbook'@'%';
FLUSH PRIVILEGES;
