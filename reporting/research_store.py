"""Validate researched facts without pretending to verify their truth automatically."""
import json
import math
from datetime import date,datetime,timezone,timedelta
from urllib.parse import urlparse
from .paths import ROOT,PRIVATE
KST=timezone(timedelta(hours=9))


def validate(data):
    if not isinstance(data,dict) or data.get('version')!=1:raise ValueError('리서치 version 1 객체가 필요합니다.')
    as_of=date.fromisoformat(data['as_of'])
    if as_of>datetime.now(KST).date():raise ValueError('미래의 조사일은 허용하지 않습니다.')
    sources=data.get('sources',{})
    for key,s in sources.items():
        u=urlparse(s['url'])
        if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('출처는 HTTPS 원문 링크여야 합니다.')
        if date.fromisoformat(s['date'])>as_of:raise ValueError('출처 발표일이 조사일보다 늦습니다.')
        if not s.get('label'):raise ValueError('출처 이름이 필요합니다.')
    def refs(ids):
        if not ids or any(k not in sources for k in ids):raise ValueError('리서치 출처 ID를 확인하세요.')
    for code,b in data.get('stocks',{}).items():
        if not code or not isinstance(b,dict):raise ValueError('종목 코드별 분석 객체가 필요합니다.')
        for key in ('sector','role','title','thesis','brief','base','up','down','watch','decision'):
            if not isinstance(b.get(key),str) or not b[key].strip():raise ValueError(f'종목 분석 {key} 누락')
        refs(b.get('sources',[]))
        if not b.get('facts'):raise ValueError('종목별 확인 사실이 필요합니다.')
        for fact in b['facts']:
            if not all(isinstance(fact.get(k),str) and fact[k] for k in ('label','value','context')):raise ValueError('실적 사실의 항목·값·기간 설명이 필요합니다.')
        fin=b.get('financials',{})
        if not isinstance(fin.get('rows'),list):raise ValueError('재무 지표 배열이 필요합니다.')
        for row in fin['rows']:
            refs([row['source']])
            if not all(row.get(k) for k in ('label','unit','period')):raise ValueError('재무 지표 단위·기간 누락')
            for k in ('value','previous'):
                n=row.get(k)
                if n is not None and (isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n)):raise ValueError('재무 지표는 유한 숫자 또는 null이어야 합니다.')
            if row.get('id')=='capex' and row.get('value') is not None and row['value']<0:raise ValueError('capex는 현금 지출의 양수 절댓값으로 입력하세요.')
            if row.get('value') is None and not row.get('missing_reason'):raise ValueError('결측 사유가 필요합니다.')
        if not isinstance(b.get('news'),list):raise ValueError('뉴스 배열이 필요합니다.')
        if not b['news'] and not b.get('news_note'):raise ValueError('뉴스 미확인 사유가 필요합니다.')
        for n in b['news']:
            refs([n['source']])
            if date.fromisoformat(n['date'])>as_of:raise ValueError('미래 뉴스는 사용할 수 없습니다.')
            if not all(n.get(k) for k in ('title','summary','impact')):raise ValueError('뉴스 사실과 분석을 구분하세요.')
    for s in data.get('sectors',{}).values():refs(s['sources'])
    for v in data.get('events',[]):
        refs([v['source']])
        if v.get('date'):date.fromisoformat(v['date'])
    return data


def load(example=False):
    path=ROOT/'examples/research.json' if example else PRIVATE/'research.json'
    if not path.exists():return {'version':1,'as_of':None,'stocks':{},'sources':{},'sectors':{},'events':[],'portfolio':{}}
    try:return validate(json.loads(path.read_text(encoding='utf-8')))
    except (KeyError,TypeError,json.JSONDecodeError) as ex:raise ValueError('리서치 파일의 필수 필드나 JSON 형식을 확인하세요.') from None
