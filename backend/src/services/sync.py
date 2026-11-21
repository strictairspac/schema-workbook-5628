"""复核库增量同步。

源库（草案/依赖）的每次成功提交，都在**同一事务**内追加一条提交记录与若干变更：
事务回滚时这些记录随之回滚，因此回滚不传出；提交序号在行锁下分配，保证已提交记录
序号连续。复核库独立存储，只保存**整笔提交完整应用后**的状态：游标、已应用提交与副本
在同一事务落库，中断后从上次游标继续；重复投递按 commit_id/seq 幂等跳过；发现缺号或
改动不全立即暂停，保留最后可核对版本。
"""
import uuid
from sqlalchemy import select,func
from fastapi import HTTPException
from src.models.entities import (Relation,Dependency,SyncClock,SyncCommit,SyncChange,
    ReviewState,ReviewRelation,ReviewDependency,ReviewAppliedCommit)
from src.utils.serialization import record
from src.config.database import Session,ReviewSession

KIND_RELATION='relation'; KIND_DEPENDENCY='dependency'

def _dialect(db):return db.get_bind().dialect.name

# ---------------------------------------------------------------- 源库：提交捕获

def relation_payload(obj):
    return {'id':obj.id,'code':obj.code,'title':obj.title,'attributes':list(obj.attributes),'note':obj.note or ''}

def dependency_payload(obj):
    return {'id':obj.id,'relation_id':obj.relation_id,'lhs':list(obj.lhs),'rhs':list(obj.rhs),'note':obj.note or ''}

def _lock_clock(db):
    stmt=select(SyncClock).where(SyncClock.id==1)
    if _dialect(db)!='sqlite':stmt=stmt.with_for_update()
    clock=db.scalar(stmt)
    if clock is None:
        clock=SyncClock(id=1,value=0);db.add(clock);db.flush()
    return clock

def ensure_clock(db):
    if db.get(SyncClock,1) is None:
        try:db.add(SyncClock(id=1,value=0));db.commit()
        except Exception:db.rollback()

def current_seq(db):
    clock=db.get(SyncClock,1)
    return clock.value if clock else 0

def capture(db,kind,op,entity_id,payload,user,action):
    """把一次变更挂到本事务的提交上；首次调用时在行锁下分配连续序号。"""
    state=db.info.get('sync_commit')
    if state is None:
        clock=_lock_clock(db)
        clock.value+=1;db.flush()
        commit_id=uuid.uuid4().hex
        commit=SyncCommit(seq=clock.value,commit_id=commit_id,actor=user.email,action=action,change_count=0)
        db.add(commit);db.flush()
        state={'commit_id':commit_id,'seq':commit.seq,'changes':0,'commit':commit};db.info['sync_commit']=state
    db.add(SyncChange(commit_seq=state['seq'],commit_id=state['commit_id'],kind=kind,entity_id=entity_id,op=op,payload=payload))
    state['changes']+=1;state['commit'].change_count=state['changes']

# ---------------------------------------------------------------- 复核库：副本读写

def _review_state(db,lock=False):
    """写路径用：取状态行，缺失则创建。"""
    stmt=select(ReviewState).where(ReviewState.id==1)
    if lock and _dialect(db)!='sqlite':stmt=stmt.with_for_update()
    state=db.scalar(stmt)
    if state is None:
        state=ReviewState(id=1,status='empty',cursor_seq=0,base_seq=0);db.add(state);db.flush()
    return state

def _peek_state(db):
    """读路径用：绝不写库，缺失时返回未落库的空状态。"""
    state=db.get(ReviewState,1)
    return state or ReviewState(id=1,status='empty',cursor_seq=0,base_seq=0,blocked_reason=None,missing_seq=None,error=None)

def _blank(state,status,reason=None,missing=None,error=None):
    state.status=status;state.blocked_reason=reason;state.missing_seq=missing;state.error=error

def _upsert(db,kind,payload,seq):
    if kind==KIND_RELATION:
        row=db.get(ReviewRelation,payload['id'])
        if row is None:row=ReviewRelation(source_id=payload['id']);db.add(row)
        row.code=payload['code'];row.title=payload['title'];row.attributes=payload['attributes'];row.note=payload.get('note','')
        row.applied_seq=seq
    else:
        row=db.get(ReviewDependency,payload['id'])
        if row is None:row=ReviewDependency(source_id=payload['id']);db.add(row)
        row.relation_source_id=payload['relation_id'];row.lhs=payload['lhs'];row.rhs=payload['rhs'];row.note=payload.get('note','')
        row.applied_seq=seq

def _delete(db,kind,entity_id):
    if kind==KIND_RELATION:
        row=db.get(ReviewRelation,entity_id)
        if row:db.delete(row)
        for dep in list(db.scalars(select(ReviewDependency).where(ReviewDependency.relation_source_id==entity_id))):db.delete(dep)
    else:
        row=db.get(ReviewDependency,entity_id)
        if row:db.delete(row)

def _apply(db,commit,changes):
    if db.get(ReviewAppliedCommit,commit.seq) is not None:return False
    if db.scalar(select(ReviewAppliedCommit).where(ReviewAppliedCommit.commit_id==commit.commit_id)):return False
    ordered=sorted(changes,key=lambda c:(0 if c.kind==KIND_RELATION else 1,c.id))
    for change in ordered:
        if change.op=='upsert':_upsert(db,change.kind,change.payload,commit.seq)
        else:_delete(db,change.kind,change.entity_id)
    db.add(ReviewAppliedCommit(seq=commit.seq,commit_id=commit.commit_id,actor=commit.actor,action=commit.action,change_count=commit.change_count))
    return True

# ---------------------------------------------------------------- 对外操作

def status_payload(review,source):
    state=_peek_state(review)
    relations=review.scalar(select(func.count()).select_from(ReviewRelation)) or 0
    dependencies=review.scalar(select(func.count()).select_from(ReviewDependency)) or 0
    source_seq=current_seq(source)
    updated=record(state)['updated_at'] if state.updated_at else None
    return {'status':state.status,'cursor_seq':state.cursor_seq,'base_seq':state.base_seq,
        'last_commit_id':state.last_commit_id,'blocked_reason':state.blocked_reason,
        'missing_seq':state.missing_seq,'error':state.error,'updated_at':updated,
        'counts':{'relations':relations,'dependencies':dependencies},
        'source_seq':source_seq,'pending':max(0,source_seq-state.cursor_seq)}

def list_relations(review):return [record(x) for x in review.scalars(select(ReviewRelation).order_by(ReviewRelation.source_id))]
def list_dependencies(review):return [record(x) for x in review.scalars(select(ReviewDependency).order_by(ReviewDependency.source_id))]
def list_commits(review,limit=100):return [record(x) for x in review.scalars(select(ReviewAppliedCommit).order_by(ReviewAppliedCommit.seq.desc()).limit(limit))]

def has_pending(source,review):
    state=_peek_state(review)
    return state.status in ('ready','syncing') and current_seq(source)>state.cursor_seq

def overview(review,source):
    return {'state':status_payload(review,source),'relations':list_relations(review),'dependencies':list_dependencies(review),'commits':list_commits(review)}

def bootstrap(source,user):
    """初次全量复制。

    在一个源库快照里同时读取提交序号与全部草案/依赖，二者严格对应；复制期间源库照常
    编辑，快照之后的提交留给增量重放。复核库整批写入同一事务，成功后一次性可见。
    """
    ensure_clock(source)
    with ReviewSession() as review:
        state=_review_state(review,lock=True)
        # 'copying' 可能是上次进程中断留下的：副本批次与游标同事务写入，重试是安全的。
        if state.status not in ('empty','copying'):
            raise HTTPException(409,'复核库已初始化，请使用“接上增量”按游标继续同步')
        for model in (ReviewDependency,ReviewRelation):
            for row in list(review.scalars(select(model))):
                review.delete(row)
        state.status='copying';state.blocked_reason=None;state.missing_seq=None;state.error=None
        review.commit()
    try:
        with Session() as src:
            base=current_seq(src)
            relations=[relation_payload(x) for x in src.scalars(select(Relation).order_by(Relation.id))]
            dependencies=[dependency_payload(x) for x in src.scalars(select(Dependency).order_by(Dependency.id))]
    except Exception as exc:
        with ReviewSession() as review:
            fresh=_review_state(review);_blank(fresh,'empty',error='读取源库失败：%s'%exc);review.commit()
        raise HTTPException(500,'读取源库失败，复核库仍为空，可重试')
    try:
        with ReviewSession() as review:
            for row in relations:_upsert(review,KIND_RELATION,row,base)
            for row in dependencies:_upsert(review,KIND_DEPENDENCY,row,base)
            fresh=_review_state(review,lock=True)
            fresh.base_seq=base;fresh.cursor_seq=base;fresh.last_commit_id=None
            with Session() as src:
                ahead=current_seq(src)>base
            _blank(fresh,'syncing' if ahead else 'ready')
            review.commit()
    except Exception as exc:
        with ReviewSession() as review:
            for model in (ReviewDependency,ReviewRelation):
                for row in list(review.scalars(select(model))):review.delete(row)
            fresh=_review_state(review);fresh.cursor_seq=0;fresh.base_seq=0
            _blank(fresh,'empty',error='初次复制失败：%s'%exc);review.commit()
        raise HTTPException(500,'初次复制失败，复核库未对外开放，可重试')
    with ReviewSession() as review, Session() as src:
        return status_payload(review,src)

def pull(source,limit=100):
    """从游标之后按序号连续应用；缺号或改动不全则暂停，保留最后可核对版本。

    每一笔提交的“读源库变更 + 应用副本 + 推进游标”都在同一个复核库事务内完成，
    全程持有状态行锁，多个同步者不会重复应用同一提交。
    """
    limit=max(1,min(int(limit),500));applied=0
    while applied<limit:
        with ReviewSession() as review:
            state=_review_state(review,lock=True)
            status,expected=state.status,state.cursor_seq+1
            review.commit()
        if status=='empty':
            raise HTTPException(409,'复核库尚未初次复制，请先执行初次复制')
        with Session() as src:
            commit=src.get(SyncCommit,expected)
            changes=list(src.scalars(select(SyncChange).where(SyncChange.commit_seq==expected).order_by(SyncChange.id))) if commit else []
            source_max=src.scalar(select(func.max(SyncCommit.seq))) or 0
        if commit is None:
            with ReviewSession() as review:
                state=_review_state(review,lock=True)
                if source_max>=expected:_blank(state,'blocked','gap',missing=expected,error='提交记录断档：缺少第 %d 号提交，已暂停在 %d 号'%(expected,state.cursor_seq))
                else:_blank(state,'ready')
                review.commit()
                with Session() as src:return status_payload(review,src)
        if len(changes)!=commit.change_count:
            with ReviewSession() as review:
                state=_review_state(review,lock=True)
                _blank(state,'blocked','incomplete',missing=expected,error='第 %d 号提交的改动未到齐（%d/%d），已暂停'%(expected,len(changes),commit.change_count))
                review.commit()
                with Session() as src:return status_payload(review,src)
        try:
            with ReviewSession() as review:
                state=_review_state(review,lock=True)
                if state.cursor_seq+1!=expected:          # 另一同步者已推进，重新取号
                    review.rollback();continue
                _apply(review,commit,changes)
                state.cursor_seq=expected;state.last_commit_id=commit.commit_id
                _blank(state,'syncing' if source_max>expected else 'ready')
                review.commit()
        except Exception as exc:
            with ReviewSession() as review:
                state=_review_state(review,lock=True)
                _blank(state,'blocked','apply_error',missing=expected,error='应用第 %d 号提交失败，已暂停：%s'%(expected,exc))
                review.commit()
            raise HTTPException(500,'应用提交失败，复核库已暂停在上一可核对版本')
        applied+=1
    with ReviewSession() as review:
        with Session() as src:
            source_max=src.scalar(select(func.max(SyncCommit.seq))) or 0
        state=_review_state(review,lock=True)
        if state.status!='blocked':_blank(state,'syncing' if state.cursor_seq<source_max else 'ready')
        review.commit()
        with Session() as src:return status_payload(review,src)

def reset(source,user):
    with ReviewSession() as review:
        for model in (ReviewDependency,ReviewRelation,ReviewAppliedCommit):
            for row in list(review.scalars(select(model))):review.delete(row)
        state=_review_state(review,lock=True);_blank(state,'empty');state.cursor_seq=0;state.base_seq=0;state.last_commit_id=None
        review.commit()
        with Session() as src:return status_payload(review,src)
