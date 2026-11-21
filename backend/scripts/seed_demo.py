from sqlalchemy import select,func
from types import SimpleNamespace
from src.config.database import Session,ReviewSession,Base,ReviewBase,engine,review_engine
from src.models.entities import User,Relation,Dependency,Report
from src.utils.security import password_hash
from src.services import sync

def seed():
    Base.metadata.create_all(engine)
    ReviewBase.metadata.create_all(review_engine)
    with Session() as db:
        for role in ('admin','operator','viewer'):
            email=role+'@nanlu.test'
            if not db.scalar(select(User).where(User.email==email)):db.add(User(email=email,password=password_hash('Demo2026!'),role=role))
        cases=[('NL-1117-A','材料检测委托单',['委托号','客户','检测项','方法','结果'],[(['委托号'],['客户']),(['检测项'],['方法']),(['委托号','检测项'],['结果'])]),('NL-1117-B','循环编号与独立属性',['A','B','C'],[(['A'],['B']),(['B'],['A'])]),('NL-1117-C','尚未确认业务依赖',['批号','容器','记录人'],[])]
        actor=SimpleNamespace(email='seed@nanlu.test')
        for code,title,attrs,fds in cases:
            rel=db.scalar(select(Relation).where(Relation.code==code))
            if rel:continue
            rel=Relation(code=code,title=title,attributes=attrs,note='南麓材料实验室 · 09:15 委托表复核');db.add(rel);db.flush()
            sync.capture(db,sync.KIND_RELATION,'upsert',rel.id,sync.relation_payload(rel),actor,'演示数据 创建关系草案 '+code)
            for lhs,rhs in fds:
                dep=Dependency(relation_id=rel.id,lhs=lhs,rhs=rhs,note='业务确认依赖');db.add(dep);db.flush()
                sync.capture(db,sync.KIND_DEPENDENCY,'upsert',dep.id,sync.dependency_payload(dep),actor,'演示数据 创建函数依赖')
        db.commit()
        print({cls.__tablename__:db.scalar(select(func.count()).select_from(cls)) for cls in (User,Relation,Dependency,Report)})
if __name__=='__main__':seed()
