import os,base64,json
from http.server import BaseHTTPRequestHandler,HTTPServer
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.services.time_evidence_service import canonical_evidence_bytes
key=Ed25519PrivateKey.generate(); print(json.dumps({"pid":os.getpid(),"public_key":base64.b64encode(key.public_key().public_bytes_raw()).decode()}),flush=True)
class H(BaseHTTPRequestHandler):
 def do_POST(self):
  n=int(self.headers.get("Content-Length",0)); req=json.loads(self.rfile.read(n)); from datetime import datetime,timezone
  out={**req,"authority_issued_at":datetime.now(timezone.utc).isoformat(),"authority_key_id":"test-time-authority","authority_uncertainty_seconds":0.1}; out["signature"]=base64.b64encode(key.sign(canonical_evidence_bytes(out))).decode(); data=json.dumps(out).encode(); self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
 def log_message(self,*a): pass
HTTPServer(("127.0.0.1",int(os.environ["TIME_AUTHORITY_PORT"])),H).serve_forever()
