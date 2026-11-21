from sqlalchemy import select,func
from fastapi import HTTPException
from src.models.entities import Relation,Dependency
from src.utils.serialization import record
from src.services import sync
from .common import save
def listing(db):return [record(x) for x in db.scalars(select(Dependency).order_by(Dependency.id))]
def validate(db,data,exclude=None):
    relation=db.get(Relation,data.relation_id)
    if not relation:raise HTTPException(404,'关系不存在')
    if not set(data.lhs+data.rhs)<=set(relation.attributes):raise HTTPException(422,'依赖属性必须属于选定关系')
    count=db.scalar(select(func.count()).select_from(Dependency).where(Dependency.relation_id==data.relation_id))
    if not exclude and count>=64:raise HTTPException(422,'最多64条函数依赖，请合并后重试')
def create(db,data,user):
    validate(db,data)
    return save(db,Dependency(**data.model_dump()),user,'创建函数依赖',
        hook=lambda s,o:sync.capture(s,sync.KIND_DEPENDENCY,'upsert',o.id,sync.dependency_payload(o),user,'创建函数依赖'))
def update(db,ident,data,user):
    obj=db.get(Dependency,ident)
    if not obj:raise HTTPException(404,'依赖不存在')
    validate(db,data,ident)
    previous_relation=obj.relation_id
    for k,v in data.model_dump().items():setattr(obj,k,v)
    def hook(s,o):
        action='更新函数依赖'
        if previous_relation!=o.relation_id:action='函数依赖迁移到关系 '+str(o.relation_id)
        sync.capture(s,sync.KIND_DEPENDENCY,'upsert',o.id,sync.dependency_payload(o),user,action)
    return save(db,obj,user,'更新函数依赖',hook=hook)
