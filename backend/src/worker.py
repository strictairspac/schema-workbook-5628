import traceback,json
from pathlib import Path
from src.config.database import Session,ReviewSession
from src.models.entities import Report
from src.services.reports import queue
from src.services.normalization import analyze
from src.services import sync

def tick_review():
    """Opportunistically advance the review copy; blocked/gap states are left untouched."""
    try:
        with Session() as src, ReviewSession() as review:
            if not sync.has_pending(src,review):return
        with Session() as src:sync.pull(src,100)
    except Exception:traceback.print_exc()

while True:
    Path('/tmp/worker-heartbeat').touch()
    item=queue.blpop('schemaworkbook:queue',timeout=2)
    if not item:
        tick_review();continue
    ident=int(item[1])
    try:
        with Session() as db:
            obj=db.get(Report,ident);obj.status='running';db.commit();snapshot=obj.input_snapshot
        result=analyze(snapshot['relation']['attributes'],snapshot['dependencies'])
        with Session() as db:
            obj=db.get(Report,ident);obj.result=result;obj.status='completed';db.commit()
        Path(f'/artifacts/report-{ident}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as e:
        traceback.print_exc()
        with Session() as db:
            obj=db.get(Report,ident)
            if obj:obj.status='failed';obj.error=str(e);db.commit()
