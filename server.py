#!/usr/bin/env python3
"""Loopback UI with launch-link authentication and a private session cookie."""
import argparse
import json
import mimetypes
import os
import secrets
import socket
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as BaseThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from reporting.engine import analyze, demo_snapshot
from reporting.provider import PlugReader, select_saved
from reporting.connection import save_verified_connection, migrate_legacy, ensure_credentials, connection_status, record_connected, ConnectionProblem
from reporting.export import html_report, markdown, email_message, newsletter
from reporting.storage import read_json, write_json
from reporting.paths import ROOT, PRIVATE

TOKEN = secrets.token_urlsafe(32)
BOOTSTRAP = secrets.token_urlsafe(32)
BOOTSTRAP_EXPIRES = time.monotonic() + 600
LOCK = threading.RLock()
reader = PlugReader()
state = {'snapshot': None, 'cached': False}


class ThreadingHTTPServer(BaseThreadingHTTPServer):
    # Windows SO_REUSEADDR permits another process to bind the same live port.
    # Exclusive binding makes port fallback reliable and prevents a stale UI.
    allow_reuse_address = os.name != 'nt'

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def selected_snapshot():
    ensure_credentials(PRIVATE)
    path = PRIVATE / 'selected-account.json'
    if not path.exists(): raise ValueError('계좌를 먼저 연결하세요.')
    saved = read_json(path)
    return reader.balance(select_saved(reader.list_accounts(), saved), saved.get('market', 'us'))


def current_report(final=False):
    if not state['snapshot']: raise ValueError('먼저 PLUG 계좌를 연결하세요.')
    r = analyze(state['snapshot'])
    if final and not r['research_status']['final_ready']:
        raise ValueError('종목 조사를 마무리한 뒤 뉴스레터와 최종 리포트를 만들 수 있습니다.')
    return r


def connect_credentials(data):
    global reader
    try:
        result = save_verified_connection(data, PRIVATE)
        reader.forget()
        reader = PlugReader(PRIVATE / 'plug-vault.json')
        state['cached'] = bool(state['snapshot'])
        return {**result, 'connection': connection_status(PRIVATE)}
    except ConnectionProblem:
        raise
    except ValueError as ex:
        raise ValueError('검증 실패 · 새 키를 저장하지 않았습니다. 기존 연결을 유지했습니다. ' + str(ex)) from None
    finally:
        data.clear()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def respond(self, data, status=200, ctype='application/json; charset=utf-8', filename=None, cookie=False):
        if isinstance(data, (dict, list)): data = json.dumps(data, ensure_ascii=False)
        if isinstance(data, str): data = data.encode('utf-8')
        self.send_response(status)
        for key, val in {'Content-Type': ctype, 'Content-Length': str(len(data)), 'Cache-Control': 'no-store',
                         'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'SAMEORIGIN',
                         'Referrer-Policy': 'no-referrer',
                         'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'; object-src 'none'"}.items():
            self.send_header(key, val)
        if cookie: self.send_header('Set-Cookie', f'plug_session={TOKEN}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200')
        if filename: self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError): pass

    def allowed(self):
        return self.headers.get('Host', '') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

    def authenticated(self):
        try:
            c = SimpleCookie(self.headers.get('Cookie', ''))
            return bool(c.get('plug_session')) and secrets.compare_digest(c['plug_session'].value, TOKEN)
        except Exception: return False

    def do_GET(self):
        if not self.allowed(): return self.respond({'error': '로컬 접속만 허용합니다.'}, 403)
        path = urlparse(self.path).path
        if path.startswith('/api/') and not self.authenticated():
            return self.respond({'error': '서버 시작 시 표시한 접속 링크로 화면을 여세요.'}, 401)
        with LOCK:
            try:
                if path == '/api/connection': return self.respond(connection_status(PRIVATE))
                if path == '/api/delivery':
                    f = PRIVATE / 'delivery.json'
                    return self.respond(read_json(f) if f.exists() else {'status': '미발송', 'gmail_url': None})
                if path == '/api/report':
                    return self.respond({'report': current_report() if state['snapshot'] else None, 'cached': state['cached'], 'connection': connection_status(PRIVATE)})
                if path == '/api/mail-preview': return self.respond(newsletter(current_report(True), detail_url='/api/export/html'), ctype='text/html; charset=utf-8')
                if path == '/api/export/eml': return self.respond(email_message(current_report(True)).as_bytes(), ctype='message/rfc822', filename='investment-report.eml')
                if path == '/api/export/md': return self.respond(markdown(current_report(True)), ctype='text/markdown; charset=utf-8', filename='investment-report.md')
                if path == '/api/export/html': return self.respond(html_report(current_report(True)), ctype='text/html; charset=utf-8')
                if path in ('/docs/prompts', '/docs/filming'):
                    f = ROOT / 'docs' / ('PROMPTS.md' if path.endswith('prompts') else 'FILMING.md')
                    return self.respond(f.read_text(encoding='utf-8'), ctype='text/plain; charset=utf-8')
                if path.startswith('/api/'): return self.respond({'error': '없는 기능입니다.'}, 404)
                dist = (ROOT / 'frontend/dist').resolve()
                f = (dist / path.lstrip('/')).resolve()
                if not f.is_relative_to(dist): return self.respond({'error': '없는 경로입니다.'}, 404)
                if path == '/': f = dist / 'index.html'
                if not f.is_file(): return self.respond('화면 파일이 없습니다. start를 다시 실행하세요.', 404, 'text/plain; charset=utf-8')
                return self.respond(f.read_bytes(), ctype=mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
            except ValueError:
                return self.respond({'error': '계좌·리서치 파일을 확인하세요. 분석 대기 항목은 최종 리포트로 내보낼 수 없습니다.'}, 400)
            except Exception:
                return self.respond({'error': '로컬 파일을 읽지 못했습니다. 설정과 접근 권한을 확인하세요.'}, 500)

    def do_POST(self):
        global BOOTSTRAP
        origin = self.headers.get('Origin')
        expected = 'http://' + self.headers.get('Host', '')
        if not self.allowed() or (origin and origin != expected) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.respond({'error': '외부 페이지 요청은 허용하지 않습니다.'}, 403)
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.respond({'error': 'JSON 요청만 허용합니다.'}, 415)
        if self.path != '/api/session' and not self.authenticated(): return self.respond({'error': '접속 링크에서 다시 시작하세요.'}, 401)
        data = {}
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 16384: return self.respond({'error': '입력 크기 제한'}, 413)
            data = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data, dict): raise ValueError('객체 형식 입력이 필요합니다.')
            with LOCK:
                if self.path == '/api/session':
                    nonce = data.get('nonce')
                    if not isinstance(nonce, str) or not BOOTSTRAP or time.monotonic() > BOOTSTRAP_EXPIRES or not secrets.compare_digest(nonce, BOOTSTRAP):
                        return self.respond({'error': '접속 링크가 만료되었거나 이미 사용됐습니다. start를 다시 실행하세요.'}, 403)
                    BOOTSTRAP = None
                    return self.respond({'ok': True}, cookie=True)
                if self.path == '/api/credentials': return self.respond(connect_credentials(data))
                if self.path == '/api/migrate':
                    result = migrate_legacy(PRIVATE, retry=True)
                    reader.forget()
                    return self.respond({**result, 'connection': connection_status(PRIVATE)})
                if self.path == '/api/accounts':
                    ensure_credentials(PRIVATE)
                    return self.respond({'accounts': reader.list_accounts()})
                if self.path == '/api/demo':
                    snap = demo_snapshot()
                elif self.path == '/api/connect':
                    market = data.get('market', 'us')
                    if data.get('ref') not in reader.accounts: reader.list_accounts()
                    snap = reader.balance(data.get('ref'), market)
                    write_json(PRIVATE / 'selected-account.json', {'account_id': snap['account_id'], 'label': snap['account_label'], 'market': market})
                elif self.path == '/api/refresh': snap = selected_snapshot()
                else: return self.respond({'error': '없는 기능입니다.'}, 404)
                report = analyze(snap)
                state.update(snapshot=snap, cached=False)
                if snap['mode'] != 'demo':
                    write_json(PRIVATE / 'last-snapshot.json', snap)
                    record_connected(PRIVATE)
                return self.respond({'report': report, 'cached': False})
        except ConnectionProblem as ex:
            self.respond({'error': str(ex), 'code': ex.code}, 400)
        except (ValueError, TypeError, KeyError) as ex:
            self.respond({'error': str(ex) if type(ex) is ValueError else '입력 형식·필수 항목을 확인하세요.'}, 400)
        except Exception:
            self.respond({'error': '처리하지 못했습니다. OS 보안 저장소와 파일 권한을 확인하세요. 새 키는 저장 여부를 확인한 뒤 다시 연결하세요.'}, 500)
        finally:
            if isinstance(data, dict): data.clear()


def restore_snapshot():
    cached = PRIVATE / 'last-snapshot.json'
    if cached.exists():
        try:
            snapshot = read_json(cached)
            if snapshot.get('mode') not in ('live', 'mock'): return
            analyze(snapshot)
            state.update(snapshot=snapshot, cached=True)
        except (OSError, ValueError, KeyError, TypeError): pass


def bind_server(port=8766):
    try: return ThreadingHTTPServer(('127.0.0.1', port), Handler)
    except OSError:
        return ThreadingHTTPServer(('127.0.0.1', 0), Handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    restore_snapshot()
    http = bind_server(args.port)
    url = f'http://127.0.0.1:{http.server_port}/#session={BOOTSTRAP}'
    write_json(PRIVATE / 'server.json', {'url': url, 'port': http.server_port, 'pid': os.getpid()})
    print('포트폴리오 리포트 접속 링크 (10분 이내, 이 PC에서만 사용): ' + url, flush=True)
    if args.open:
        import webbrowser
        webbrowser.open(url)
    try: http.serve_forever()
    except KeyboardInterrupt: pass
    finally: reader.forget(); http.server_close()


if __name__ == '__main__': main()
