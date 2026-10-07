"""Local dashboard + public webpage reader. No account credentials."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs
import json,mimetypes,re
from public_data import REGISTRY,refresh
from music_data import refresh_music
ROOT = Path(__file__).resolve().parent
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        hosts=('127.0.0.1:8766','localhost:8766')
        if self.headers.get('Host') not in hosts:
            self.send_error(403);return
        origin=self.headers.get('Origin')
        if origin and origin not in ('http://'+h for h in hosts):
            self.send_error(403);return
        parts=urlsplit(self.path)
        if parts.path=='/api/music':
            self.respond(json.dumps(refresh_music(),ensure_ascii=False).encode(),'application/json; charset=utf-8');return
        if parts.path=='/api/public/profile':
            query=parse_qs(parts.query);uid=query.get('uid',[''])[0];name=query.get('name',[''])[0];ident=query.get('id',[''])[0]
            if not re.fullmatch(r'\d{5,20}',uid) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',ident) or not 1<=len(name)<=100:
                self.send_error(400);return
            entry=next((e for e in REGISTRY if e['uid']==uid),None)
            if entry is None:entry={'id':ident,'uid':uid,'name':name,'aliases':[name]}
            body=json.dumps(refresh(entry),ensure_ascii=False).encode()
            self.respond(body,'application/json; charset=utf-8');return
        name=unquote(parts.path).lstrip('/') or 'index.html';path=(ROOT/name).resolve()
        allowed=name in {'index.html','style.css','app.js','data.js','public-data.js','music-data.js'} or name.startswith('screenshots/')
        if not allowed or ROOT not in path.parents or not path.is_file():self.send_error(404);return
        self.respond(path.read_bytes(),mimetypes.guess_type(path)[0] or 'application/octet-stream')
    def respond(self,raw,mime):
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-cache');self.end_headers();self.wfile.write(raw)
    def log_message(self,*_):pass
if __name__=='__main__':
    print('音浪公开资料看板：http://127.0.0.1:8766',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
