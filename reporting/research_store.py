"""Validate researched facts without pretending to verify their truth automatically."""
import json
import math
from datetime import date,datetime,timezone,timedelta
from urllib.parse import urlparse
from .paths import ROOT,PRIVATE
KST=timezone(timedelta(hours=9))


def validate(data):
    if not isinstance(data,dict) or data.get('version')!=2:raise ValueError('리서치 version 2 객체가 필요합니다.')
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
    from .identity import identity, SECTORS
    resolved = set()
    for code,b in data.get('stocks',{}).items():
        if not code or not isinstance(b,dict):raise ValueError('종목 코드별 분석 객체가 필요합니다.')
        parts = code.split('|')
        if len(parts) != 4 or identity(*parts) != code: raise ValueError('종목 키는 시장|거래소|코드|상품종류 형식이어야 합니다.')
        status = b.get('status')
        if status not in ('pending', 'verified', 'unresolved'): raise ValueError('종목 조사 상태가 필요합니다.')
        if status == 'pending': continue
        refs(b.get('sources'))
        if status == 'unresolved':
            if not b.get('reason') or not b.get('checked_at'): raise ValueError('미확인 사유·확인일·확인한 출처가 필요합니다.')
            if date.fromisoformat(b['checked_at']) != as_of: raise ValueError('미확인 항목도 조사일에 재확인하세요.')
            continue
        i = b.get('identity', {})
        actual = identity(i.get('market'), i.get('exchange'), i.get('code'), i.get('product_type'))
        aparts = actual.split('|')
        if 'UNKNOWN' in aparts: raise ValueError('검증 완료 종목은 거래소·상품 종류까지 확인하세요.')
        refs(b.get('identity_sources'))
        for index in (0, 1, 3):
            if parts[index] != 'UNKNOWN' and parts[index] != aparts[index]: raise ValueError('보유와 조사 종목의 시장·거래소·상품 종류가 다릅니다.')
        if parts[2] != aparts[2]:
            alias = b.get('code_alias', {})
            if alias.get('from') != parts[2] or alias.get('to') != aparts[2]: raise ValueError('종목 코드 별칭은 명시적인 원문 확인이 필요합니다.')
            refs(alias.get('sources'))
        if actual in resolved: raise ValueError('서로 다른 보유 종목을 동일한 증권으로 병합할 수 없습니다.')
        resolved.add(actual)
        sid = b.get('sector_id')
        if sid not in SECTORS or sid not in data.get('sectors', {}): raise ValueError('고정 섹터 ID와 섹터 분석 정의가 필요합니다.')
        if b.get('sector') != SECTORS[sid] or not b.get('classification_basis'): raise ValueError('섹터 이름·분류 근거를 확인하세요. 테마를 업종으로 사용하지 않습니다.')
        refs(b.get('classification_sources'))
        fin_kind = b.get('financials', {}).get('kind')
        if fin_kind not in ('company', 'fund'): raise ValueError('기업 또는 펀드 재무 지표 종류를 지정하세요.')
        if (i['product_type'] in ('ETF','ETN','FUND')) != (fin_kind == 'fund'): raise ValueError('ETF·펀드와 일반 기업의 지표를 혼용하지 마세요.')
        if not b.get('financials', {}).get('rows'): raise ValueError('종목별 재무 지표 또는 결측 사유를 작성하세요.')
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
    for sid,s in data.get('sectors',{}).items():
        if sid not in SECTORS or s.get('label') != SECTORS[sid] or not s.get('outlook') or not s.get('watch'): raise ValueError('섹터 정의·전망·확인 지표를 작성하세요.')
        refs(s['sources'])
    for v in data.get('events',[]):
        refs([v['source']])
        if v.get('date'):date.fromisoformat(v['date'])
    return data


def load(example=False):
    path=ROOT/'examples/research.json' if example else PRIVATE/'research.json'
    if not path.exists():return {'version':2,'as_of':None,'stocks':{},'sources':{},'sectors':{},'events':[],'portfolio':{}}
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('version') != 2: return {'version':2,'as_of':None,'stocks':{},'sources':{},'sectors':{},'events':[],'portfolio':{},'migration_required':True}
        return validate(data)
    except (KeyError,TypeError,json.JSONDecodeError) as ex:raise ValueError('리서치 파일의 필수 필드나 JSON 형식을 확인하세요.') from None
