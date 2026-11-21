import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .settings import DATABASE_URL, REVIEW_DATABASE_URL

class Base(DeclarativeBase): pass

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)

def db_session():
    with Session() as db: yield db

# 复核库使用独立引擎；未配置 REVIEW_DATABASE_URL 时与源库同库但表结构独立。
class ReviewBase(DeclarativeBase): pass
review_engine = create_engine(REVIEW_DATABASE_URL, pool_pre_ping=True)
ReviewSession = sessionmaker(review_engine, expire_on_commit=False)

def review_session():
    with ReviewSession() as db: yield db
