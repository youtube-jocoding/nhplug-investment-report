#!/usr/bin/env python3
"""Collect → Codex researches → prepare → Gmail plugin sends → record receipt.
No SMTP, model API key, scheduler daemon, or securities orders.
"""
import argparse,hashlib,json,os,re,uuid
from datetime import datetime,timedelta
from pathlib import Path
from urllib.parse import quote
from reporting.paths import PRIVATE
from reporting.engine import KST,analyze,demo_snapshot
from reporting.research_store import load
from reporting.provider import PlugReader
from reporting.export import save_report,newsletter,html_report,subject_for

def write(path,data):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    tmp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    os.replace(tmp,path)

def collect():
    selected=PRIVATE/'selected-account.json'
    if not selected.exists():raise ValueError('로컬 화면에서 PLUG 키와 계좌를 연결하세요.')
    settings=json.loads(selected.read_text());reader=PlugReader()
    accounts=[a for a in reader.list_accounts() if a['label']==settings['label']]
    if len(accounts)!=1:raise ValueError('저장한 계좌를 식별하지 못했습니다. 화면에서 다시 선택하세요.')
    snap=reader.balance(accounts[0]['ref'],settings.get('market','us'))
    if snap['mode']!='live':raise ValueError('정기 발송에는 실제 계좌가 필요합니다.')
    write(PRIVATE/'last-snapshot.json',snap)
    brief={'fetched_at':snap['fetched_at'],'market':snap.get('market','kr'),'holdings':[{'code':h['code'],'name':h['name']} for h in snap['holdings']],'instructions':'WORKFLOW.md에 따라 현재 날짜의 공식 실적·공시·최근 뉴스를 조사하고 private/research.json 작성. 기존 파일의 날짜만 바꾸지 않음.'}
    write(PRIVATE/'research-brief.json',brief)
    return {'status':'collected','brief':str(PRIVATE/'research-brief.json'),'holdings':len(snap['holdings'])}

def check_fresh(s,data,now=None):
    now=now or datetime.now(KST)
    if s['mode']!='live':raise ValueError('가상·모의 잔고는 자동 발송하지 않습니다.')
    fetched=datetime.fromisoformat(s['fetched_at'])
    if fetched.tzinfo is None:raise ValueError('조회시각의 시간대가 필요합니다.')
    if not 0<=(now-fetched).total_seconds()<=3600:raise ValueError('1시간 이내 실제 잔고를 다시 조회하세요.')
    if data.get('as_of')!=now.date().isoformat():raise ValueError('오늘 공식 자료와 뉴스를 다시 조사해야 합니다.')
    for h in s['holdings']:
        b=data.get('stocks',{}).get(h['code'])
        if not b or not b.get('financials',{}).get('rows') or not b.get('brief'):raise ValueError('모든 보유 종목의 분석·재무 항목·한 줄 요약을 작성하세요. 미확인 값은 사유를 명시합니다.')

def prepare(recipient,revision=None):
    if revision is not None and not re.fullmatch(r"[a-z0-9-]{1,40}",revision):raise ValueError("수정 발송 식별자를 확인하세요.")
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',recipient):raise ValueError('Gmail 프로필에서 확인한 본인 이메일이 필요합니다.')
    s=json.loads((PRIVATE/'last-snapshot.json').read_text());data=load();check_fresh(s,data)
    today=datetime.now(KST).date().isoformat()
    key=hashlib.sha256((today+'|'+recipient.lower()+'|'+s['account_label']+'|'+s.get('market','kr')+('|revision:'+revision if revision else '')).encode()).hexdigest()[:20]
    ledger=PRIVATE/'delivery-ledger'/f'{key}.json'
    if ledger.exists():raise ValueError('오늘 발송 시도가 이미 기록되어 있습니다. Gmail에서 확인하고 자동 재발송하지 마세요.')
    run=today+'-'+uuid.uuid4().hex[:8];folder=PRIVATE/'reports'/run
    r=analyze(s,data);save_report(r,folder)
    subject=subject_for(today)
    day=datetime.now(KST).date()
    query=f'in:sent from:me to:me subject:"내 투자 브리핑" subject:"{day.month}월 {day.day}일" after:{(day-timedelta(days=1)).strftime("%Y/%m/%d")} before:{(day+timedelta(days=1)).strftime("%Y/%m/%d")}'
    payload={'to':'me','subject':subject,'payload':{'mime_type':'multipart/mixed','parts':[{'mime_type':'text/html','charset':'utf-8','body':{'content':newsletter(r,attachment=True)}},{'mime_type':'text/html','charset':'utf-8','filename':'report.html','content_disposition':'attachment','body':{'content':html_report(r)}}]},'response_fields':['id','thread_id','label_ids']}
    write(folder/'gmail-payload.json',payload)
    digest=hashlib.sha256((folder/'gmail-payload.json').read_bytes()).hexdigest()
    manifest={'run':run,'key':key,'recipient':recipient.lower(),'subject':subject,'search_query':query,'revision':revision,'payload_sha256':digest,'status':'prepared','prepared_at':datetime.now(KST).isoformat()}
    write(folder/'manifest.json',manifest)
    return {'status':'prepared','run':run,'manifest':str(folder/'manifest.json'),'gmail_payload':str(folder/'gmail-payload.json'),'search_query':query}

def manifest_for(run):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}-[a-f0-9]{8}',run):raise ValueError('실행 ID 형식이 잘못되었습니다.')
    folder=PRIVATE/'reports'/run;m=json.loads((folder/'manifest.json').read_text())
    if hashlib.sha256((folder/'gmail-payload.json').read_bytes()).hexdigest()!=m['payload_sha256']:raise ValueError('준비 이후 메일 내용이 바뀌었습니다.')
    return folder,m

def claim(run):
    folder,m=manifest_for(run)
    if (datetime.now(KST)-datetime.fromisoformat(m['prepared_at'])).total_seconds()>3600:raise ValueError('발송 준비 후 1시간 경과. 다시 준비하세요.')
    ledger=PRIVATE/'delivery-ledger'/f'{m["key"]}.json';ledger.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    m.update(status='sending',claimed_at=datetime.now(KST).isoformat())
    try:fd=os.open(ledger,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise ValueError('발송 시도가 이미 기록되었습니다. 불확실한 발송을 자동 재시도하지 않습니다.') from None
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(m,f,ensure_ascii=False)
    return {'status':'claimed','run':run,'gmail_payload':str(folder/'gmail-payload.json')}

def sent(run,message_id):
    _,m=manifest_for(run);ledger=PRIVATE/'delivery-ledger'/f'{m["key"]}.json'
    state=json.loads(ledger.read_text())
    if state['run']!=run or state['status']!='sending':raise ValueError('이 실행의 발송 시도 기록을 확인할 수 없습니다.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{5,256}',message_id):raise ValueError('Gmail 성공 응답의 메시지 ID가 필요합니다.')
    state.update(status='sent',message_id=message_id,sent_at=datetime.now(KST).isoformat())
    write(ledger,state)
    result={'status':'sent','sent_at':state['sent_at'],'message_id':message_id,'run':run,'gmail_url':'https://mail.google.com/mail/u/0/#search/'+quote(m.get('search_query','in:sent subject:PLUG-'+m['key']).replace('in:sent','in:anywhere'),safe='')}
    write(PRIVATE/'delivery.json',result);return result

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('collect');sub.add_parser('demo');sub.add_parser('render')
    x=sub.add_parser('prepare');x.add_argument('--recipient',required=True);x.add_argument('--revision',help='사용자가 명시적으로 요청한 수정본 발송에만 사용. 정기 실행에서 사용 금지.')
    x=sub.add_parser('claim');x.add_argument('run')
    x=sub.add_parser('sent');x.add_argument('run');x.add_argument('--message-id',required=True)
    a=p.parse_args()
    if a.command=='collect':result=collect()
    elif a.command=='prepare':result=prepare(a.recipient,a.revision)
    elif a.command=='claim':result=claim(a.run)
    elif a.command=='sent':result=sent(a.run,a.message_id)
    else:
        snap=demo_snapshot() if a.command=='demo' else json.loads((PRIVATE/'last-snapshot.json').read_text())
        folder=PRIVATE/'preview';save_report(analyze(snap),folder);result={'report':str(folder/'report.html'),'newsletter':str(folder/'newsletter.html')}
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except Exception as ex:
        print(json.dumps({'error':str(ex) if isinstance(ex,ValueError) else '설정·파일·연결 상태를 확인하세요. 원문 오류는 민감정보 보호를 위해 숨겼습니다.'},ensure_ascii=False));raise SystemExit(1)
