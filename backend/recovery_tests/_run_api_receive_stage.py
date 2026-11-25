import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.sync_transport_service import SyncTransportService
original = SyncTransportService.receive_batch
stage = os.environ.get("STAGE4_RECEIVE_FAILURE_STAGE")
used = False
def fail_once(self, db, *args, **kwargs):
    global used
    if not used:
        used = True; kwargs["_failure_stage"] = stage
    return original(self, db, *args, **kwargs)
SyncTransportService.receive_batch = fail_once
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8892")))
