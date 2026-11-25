import os,time,requests
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlsplit
G=os.environ['PROXY_GATE']; R=os.environ['PROXY_RELEASE']; TARGET=os.environ['PROXY_TARGET']; timeout=float(os.environ.get('PROXY_TIMEOUT','30'))
class H(BaseHTTPRequestHandler):
 def do_POST(self):
  n=int(self.headers.get('Content-Length','0')); body=self.rfile.read(n)
  open(G,'w').close(); end=time.time()+timeout
  while not os.path.exists(R) and time.time()<end: time.sleep(.05)
  if not os.path.exists(R): self.send_error(504); return
  u=TARGET.rstrip('/')+urlsplit(self.path).path
  hdr={k:v for k,v in self.headers.items() if k.lower() not in ('host','content-length')}
  x=requests.post(u,data=body,headers=hdr,timeout=30)
  self.send_response(x.status_code); self.send_header('Content-Type',x.headers.get('Content-Type','application/json')); self.end_headers(); self.wfile.write(x.content)
 def log_message(self,*a): pass
HTTPServer(('127.0.0.1',int(os.environ.get('PROXY_PORT','8903'))),H).serve_forever()
