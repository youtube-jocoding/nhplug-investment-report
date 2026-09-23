#!/usr/bin/env python3
import json
import mimetypes
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from reporting.engine import analyze, demo_snapshot
from reporting.provider import PlugReader
from reporting.credentials import credential_environment, save_credentials
from reporting.export import html_report, markdown, email_message, save_report, newsletter
from reporting.archive import load_archive

ROOT=Path(__file__).resolve().parent
from reporting.paths import PRIVATE
TOKEN=secrets.token_urlsafe(32)
LOCK=threading.RLock()
reader=PlugReader()
state={'snapshot':demo_snapshot()}


def save_private(name,data):
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    path=PRIVATE/name
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False)


def selected_snapshot():
    path=PRIVATE/'selected-account.json'
    if not path.exists():raise ValueError('계좌를 먼저 연결하세요.')
    saved=json.loads(path.read_text(encoding='utf-8'))
    matches=[a for a in reader.list_accounts() if a['label']==saved['label']]
    if len(matches)!=1:raise ValueError('저장한 계좌 식별이 모호합니다. 계좌를 다시 선택하세요.')
    return reader.balance(matches[0]['ref'],saved.get('market','kr'))


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def respond(self,data,status=200,ctype='application/json; charset=utf-8',filename=None):
        if isinstance(data,(dict,list)): data=json.dumps(data,ensure_ascii=False)
        if isinstance(data,str): data=data.encode()
        self.send_response(status)
        self.send_header('Content-Type',ctype)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','SAMEORIGIN')
        self.send_header('Referrer-Policy','no-referrer')
        if filename: self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers(); self.wfile.write(data)
    def allowed(self):
        host=self.headers.get('Host','')
        return host in {'127.0.0.1:8766','localhost:8766','127.0.0.1:5176','localhost:5176'}
    def do_GET(self):
        if not self.allowed(): return self.respond({'error':'로컬 접속만 허용합니다.'},403)
        path=urlparse(self.path).path
        with LOCK:
            try:
                if path=='/api/delivery':
                    f=PRIVATE/'delivery.json'
                    return self.respond(json.loads(f.read_text(encoding='utf-8')) if f.exists() else {'status':'미발송','gmail_url':None})
                if path=='/api/archive': return self.respond({'entries':load_archive()})
                if path=='/api/report': return self.respond({'report':analyze(state['snapshot']),'token':TOKEN})
                if path=='/api/mail-preview': return self.respond(newsletter(analyze(state['snapshot']),detail_url='/api/export/html'),ctype='text/html; charset=utf-8')
                if path=='/api/export/eml': return self.respond(email_message(analyze(state['snapshot'])).as_bytes(),ctype='message/rfc822',filename='investment-note.eml')
                if path=='/api/export/md': return self.respond(markdown(analyze(state['snapshot'])),ctype='text/markdown; charset=utf-8',filename='investment-note.md')
                if path=='/api/export/html': return self.respond(html_report(analyze(state['snapshot'])),ctype='text/html; charset=utf-8')
                if path in ('/docs/prompts','/docs/filming'):
                    f=ROOT/'docs'/('PROMPTS.md' if path.endswith('prompts') else 'FILMING.md')
                    return self.respond(f.read_text(encoding='utf-8'),ctype='text/plain; charset=utf-8')
                if path.startswith('/api/'): return self.respond({'error':'없는 기능입니다.'},404)
                dist=(ROOT/'frontend/dist').resolve()
                f=(dist/path.lstrip('/')).resolve()
                if not f.is_relative_to(dist): return self.respond({'error':'없는 경로입니다.'},404)
                if not f.is_file(): f=dist/'index.html'
                if not f.exists(): return self.respond('화면 빌드가 필요합니다. ./start 를 실행하세요.',503,'text/plain; charset=utf-8')
                return self.respond(f.read_bytes(),ctype=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
            except ValueError as ex: return self.respond({'error':str(ex)},400)
    def do_POST(self):
        global reader
        if not self.allowed() or not secrets.compare_digest(self.headers.get('X-Report-Token',''),TOKEN):
            return self.respond({'error':'유효한 로컬 화면에서 다시 시도하세요.'},403)
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://127.0.0.1:8766','http://localhost:8766','http://127.0.0.1:5176','http://localhost:5176'}:
            return self.respond({'error':'외부 페이지 요청은 허용하지 않습니다.'},403)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<=length<=8192: return self.respond({'error':'입력 크기 제한'},413)
            data=json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data,dict): raise ValueError('객체 형식 입력이 필요합니다.')
            with LOCK:
                if self.path=='/api/demo':
                    state.update(snapshot=demo_snapshot())
                    report=analyze(state['snapshot'])
                elif self.path=='/api/credentials':
                    candidate_env=credential_environment(data)
                    old_env={key:os.environ.get(key) for key in candidate_env}
                    os.environ.update(candidate_env)
                    candidate=PlugReader(credential_path=False)
                    try:
                        accounts=candidate.list_accounts()
                        save_credentials(data,PRIVATE/'plug-credentials.json')
                    except Exception:
                        for key,value in old_env.items():
                            if value is None:os.environ.pop(key,None)
                            else:os.environ[key]=value
                        raise
                    reader=candidate
                    return self.respond({'accounts':accounts,'saved':True})
                elif self.path=='/api/accounts': return self.respond({'accounts':reader.list_accounts()})
                elif self.path=='/api/connect':
                    market=data.get('market','kr')
                    snap=reader.balance(data.get('ref'),market)
                    report=analyze(snap)
                    state['snapshot']=snap
                    save_private('selected-account.json',{'label':snap['account_label'],'market':market})
                elif self.path=='/api/refresh':
                    snap=selected_snapshot()
                    report=analyze(snap)
                    state['snapshot']=snap
                else: return self.respond({'error':'없는 기능입니다.'},404)
                save_report(report,ROOT/'output' if report['snapshot']['mode']=='demo' else PRIVATE/'latest')
                if report['snapshot']['mode']!='demo':
                    save_private('last-snapshot.json',state['snapshot'])
                self.respond({'report':report})
        except (ValueError,TypeError,KeyError) as ex:
            # No upstream raw response or exception including credentials is exposed.
            self.respond({'error':str(ex) if isinstance(ex,ValueError) else '입력 항목을 확인하세요.'},400)
        except Exception:
            self.respond({'error':'처리하지 못했습니다. 로컬 설정을 확인하고 다시 시도하세요.'},500)

if __name__=='__main__':
    # Restore a dated local snapshot, never misrepresent it as a fresh API call.
    cached=PRIVATE/'last-snapshot.json'
    if cached.exists():
        try:
            snapshot=json.loads(cached.read_text(encoding='utf-8'))
            analyze(snapshot)
            state.update(snapshot=snapshot)
        except (ValueError,KeyError,TypeError):pass
    print('투자 컨설팅 리포트: http://127.0.0.1:8766 (화면의 조회시각을 확인하세요)')
    ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
