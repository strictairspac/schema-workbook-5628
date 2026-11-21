from sqlalchemy import Column,Integer,String,JSON,DateTime,ForeignKey,Text,Index
from datetime import datetime,timezone
from src.config.database import Base,ReviewBase
def now():return datetime.now(timezone.utc)

# ---------------- 源库（实验册） ----------------
class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True);email=Column(String(120),unique=True,nullable=False);password=Column(String(300),nullable=False);role=Column(String(20),nullable=False)
class Relation(Base):
    __tablename__='relations'
    id=Column(Integer,primary_key=True);code=Column(String(80),unique=True,nullable=False);title=Column(String(160),nullable=False);attributes=Column(JSON,nullable=False);note=Column(String(300),default='')
class Dependency(Base):
    __tablename__='dependencies'
    id=Column(Integer,primary_key=True);relation_id=Column(Integer,ForeignKey('relations.id'),nullable=False);lhs=Column(JSON,nullable=False);rhs=Column(JSON,nullable=False);note=Column(String(300),default='')
class Report(Base):
    __tablename__='reports'
    id=Column(Integer,primary_key=True);name=Column(String(120),nullable=False);relation_id=Column(Integer,ForeignKey('relations.id'),nullable=False)
    status=Column(String(20),nullable=False,default='queued');input_snapshot=Column(JSON,nullable=False);result=Column(JSON,nullable=True);error=Column(Text,nullable=True)
    created_at=Column(DateTime(timezone=True),default=now)
class Audit(Base):
    __tablename__='audit_logs'
    id=Column(Integer,primary_key=True);actor=Column(String(120),nullable=False);action=Column(String(160),nullable=False);created_at=Column(DateTime(timezone=True),default=now)

# 提交日志与业务写入同一事务落盘：回滚的事务不会留下记录。
class SyncClock(Base):
    __tablename__='sync_clock'
    id=Column(Integer,primary_key=True);value=Column(Integer,nullable=False,default=0)
class SyncCommit(Base):
    """A source transaction that touched a synced entity. seq is dense and allocated under a row lock."""
    __tablename__='sync_commits'
    seq=Column(Integer,primary_key=True);commit_id=Column(String(64),unique=True,nullable=False)
    actor=Column(String(120),nullable=False);action=Column(String(200),nullable=False);change_count=Column(Integer,nullable=False,default=0)
    created_at=Column(DateTime(timezone=True),default=now)
class SyncChange(Base):
    __tablename__='sync_changes'
    id=Column(Integer,primary_key=True,autoincrement=True)
    commit_seq=Column(Integer,ForeignKey('sync_commits.seq'),nullable=False,index=True)
    commit_id=Column(String(64),nullable=False,index=True)
    kind=Column(String(20),nullable=False)          # relation | dependency
    entity_id=Column(Integer,nullable=False)
    op=Column(String(10),nullable=False)             # upsert | delete
    payload=Column(JSON,nullable=False)
    __table_args__=(Index('ix_sync_changes_commit_entity','commit_seq','kind','entity_id'),)

# ---------------- 复核库（独立存储） ----------------
# 只保存已完整应用的提交；读到的永远是最近一次可核对的版本。
class ReviewState(ReviewBase):
    __tablename__='review_state'
    id=Column(Integer,primary_key=True)
    status=Column(String(20),nullable=False,default='empty')   # empty|copying|syncing|ready|blocked
    cursor_seq=Column(Integer,nullable=False,default=0)        # 已落库的最后一个提交序号
    base_seq=Column(Integer,nullable=False,default=0)          # 初次复制所基于的提交序号
    last_commit_id=Column(String(64),nullable=True)
    blocked_reason=Column(String(20),nullable=True)            # gap|incomplete|apply_error
    missing_seq=Column(Integer,nullable=True)
    error=Column(Text,nullable=True)
    updated_at=Column(DateTime(timezone=True),default=now,onupdate=now)
class ReviewRelation(ReviewBase):
    __tablename__='review_relations'
    source_id=Column(Integer,primary_key=True)
    code=Column(String(80),nullable=False)
    title=Column(String(160),nullable=False)
    attributes=Column(JSON,nullable=False)
    note=Column(String(300),default='')
    applied_seq=Column(Integer,nullable=False,default=0)
    updated_at=Column(DateTime(timezone=True),default=now,onupdate=now)
class ReviewDependency(ReviewBase):
    __tablename__='review_dependencies'
    source_id=Column(Integer,primary_key=True)
    relation_source_id=Column(Integer,nullable=False,index=True)
    lhs=Column(JSON,nullable=False)
    rhs=Column(JSON,nullable=False)
    note=Column(String(300),default='')
    applied_seq=Column(Integer,nullable=False,default=0)
    updated_at=Column(DateTime(timezone=True),default=now,onupdate=now)
class ReviewAppliedCommit(ReviewBase):
    __tablename__='review_applied_commits'
    seq=Column(Integer,primary_key=True)
    commit_id=Column(String(64),unique=True,nullable=False)
    actor=Column(String(120),nullable=False)
    action=Column(String(200),nullable=False)
    change_count=Column(Integer,nullable=False,default=0)
    applied_at=Column(DateTime(timezone=True),default=now)
