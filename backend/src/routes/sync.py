from fastapi import APIRouter,Depends
from typing import Optional
from pydantic import BaseModel,Field
from src.config.database import db_session,review_session
from src.utils.security import current,writer,admin
from src.services import sync
router=APIRouter()
class PullInput(BaseModel):
    limit:int=Field(default=100,ge=1,le=500)
@router.get('/sync/status')
def status(db=Depends(db_session),review=Depends(review_session),user=Depends(current)):return sync.status_payload(review,db)
@router.post('/sync/bootstrap',status_code=201)
def bootstrap(db=Depends(db_session),user=Depends(writer)):return sync.bootstrap(db,user)
@router.post('/sync/pull')
def pull(data:Optional[PullInput]=None,db=Depends(db_session),user=Depends(writer)):
    return sync.pull(db,(data or PullInput()).limit)
@router.post('/sync/reset')
def reset(db=Depends(db_session),user=Depends(admin)):return sync.reset(db,user)
@router.get('/review/overview')
def overview(db=Depends(db_session),review=Depends(review_session),user=Depends(current)):return sync.overview(review,db)
@router.get('/review/relations')
def relations(review=Depends(review_session),user=Depends(current)):return sync.list_relations(review)
@router.get('/review/dependencies')
def dependencies(review=Depends(review_session),user=Depends(current)):return sync.list_dependencies(review)
@router.get('/review/commits')
def commits(review=Depends(review_session),user=Depends(current)):return sync.list_commits(review)
