import os
DATABASE_URL=os.getenv('DATABASE_URL','mysql+pymysql://schemaworkbook:schemaworkbook_demo_pw@localhost:17743/schemaworkbook')
# 复核库默认与源库同实例、同库（表独立）；生产可指向独立数据库实现物理隔离。
REVIEW_DATABASE_URL=os.getenv('REVIEW_DATABASE_URL',DATABASE_URL)
REDIS_URL=os.getenv('REDIS_URL','redis://redis:6379/0')
JWT_SECRET=os.getenv('JWT_SECRET','local-schema-workbook-change-before-public-use')
