import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.sync_transport_service import SyncTransportService
_original=SyncTransportService.receive_batch
_used=False
def _fail_once(self, db, *args, **kwargs):
    global _used
    if not _used:
        _used=True; kwargs['_fail_before_commit']=True
    return _original(self, db, *args, **kwargs)
SyncTransportService.receive_batch=_fail_once
import uvicorn
from app.main import app
uvicorn.run(app,host='127.0.0.1',port=8872)

