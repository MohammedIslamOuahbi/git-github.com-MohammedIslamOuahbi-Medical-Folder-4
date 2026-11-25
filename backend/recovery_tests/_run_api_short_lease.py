import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app.services.sync_transport_service as transport
transport.DELIVERY_LEASE_SECONDS = 5
import uvicorn
from app.main import app
uvicorn.run(app,host='127.0.0.1',port=8881)
