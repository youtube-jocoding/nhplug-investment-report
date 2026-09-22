"""Apply only research for the current holding; never substitute sample facts."""
from copy import deepcopy
from datetime import datetime,date
from .engine import KST,joint_shock

def enrich(s,data):
    for h in s['holdings']:
        b=data.get('stocks',{}).get(h['code'])
        if b:h.update(sector=b['sector'],sector_source='공식 사업 자료에 근거한 분석용 분류 · GICS 아님')
    return s

def financials(b):
    fin=deepcopy(b.get('financials',{'rows':[]}))
    rows=fin['rows']
    for row in rows:
        prev=row.get('previous');val=row.get('value')
        row['yoy']=((val/prev)-1)*100 if val is not None and prev is not None and prev>0 and row.get('comparison')=='YoY' and row.get('unit')!='%' else None
    byid={x.get('id'):x for x in rows}
    def compatible(a,b):return a and b and a.get('value') is not None and b.get('value') is not None and a['period']==b['period'] and a['unit']==b['unit']
    rev=byid.get('revenue');op=byid.get('operating_income')
    fin['operating_margin']=op['value']/rev['value']*100 if compatible(rev,op) and rev['value'] else None
    cf=byid.get('operating_cash_flow');capex=byid.get('capex')
    fin['simple_fcf']=cf['value']-capex['value'] if compatible(cf,capex) else None
    fin['fcf_unit']=cf['unit'] if cf else None
    fin['fcf_period']=cf['period'] if cf else None
    return fin

def build_consultation(r,data):
    today=datetime.now(KST).date();asof=data.get('as_of')
    groups={}
    for h in r['snapshot']['holdings']:
        g=groups.setdefault(h['code'],{**h,'value':0,'pnl':0,'cost':0})
        g['value']+=h['value']
        for k in ('pnl','cost'):g[k]=None if g[k] is None or h.get(k) is None else g[k]+h[k]
    cards=[]
    for h in sorted(groups.values(),key=lambda x:-x['value']):
        b=deepcopy(data.get('stocks',{}).get(h['code']))
        if b:b['financials']=financials(b)
        cards.append({**h,'weight':h['value']/r['total']*100,'equity_weight':h['value']/r['invested']*100 if r['invested'] else 0,'research':b})
    portfolio=data.get('portfolio',{}) if set(data.get('stocks',{}))==set(groups) else {}
    theme=sum(h['value'] for h in cards if h['code'] in portfolio.get('theme_codes',[]))
    news=[];seen=set()
    for h in cards:
        for n in (h['research'] or {}).get('news',[]):
            key=(n['source'],n['title'])
            if key in seen:continue
            seen.add(key);news.append({**n,'code':h['code'],'recent':0<=(today-date.fromisoformat(n['date'])).days<=7})
    events=[{**v,'status':'예정 · 변경 가능' if v.get('date') and v['date']>=today.isoformat() else '발표일 재확인 필요'} for v in data.get('events',[]) if not v.get('codes') or any(c in groups for c in v['codes'])]
    sectors=[{**g,**data['sectors'][g['name']],'equity_weight':g['value']/r['invested']*100 if r['invested'] else 0} for g in r['allocation'] if g['name'] in data.get('sectors',{})]
    return {'as_of':asof,'stale':not asof or asof!=today.isoformat(),'headline':portfolio.get('headline','공식 자료를 연결하면 기업 분석을 시작합니다.'),'summary':portfolio.get('summary','Codex가 보유 종목의 최신 공시와 뉴스를 조사한 뒤 이 화면에 반영합니다.'),'cards':cards,'coverage':sum(bool(c['research']) for c in cards),'count':len(cards),'sectors':sectors,'events':events,'news':sorted(news,key=lambda n:n['date'],reverse=True),'sources':data.get('sources',{}),'theme_label':portfolio.get('theme_label'),'theme_equity_weight':theme/r['invested']*100 if r['invested'] else 0,'theme_note':'사업상 공통 노출에 대한 정성 분류이며 매출 비중이나 상관계수가 아닙니다.','valuation':'실시간 가치평가 배수와 컨센서스를 연결하지 않은 경우 적정주가를 산출하지 않습니다. 성장 전망과 현재 가격의 매력은 별도로 판단해야 합니다.','scenarios':{f'{s}:{fx}':{'change':joint_shock(r['invested'],s,fx),'weight':joint_shock(r['invested'],s,fx)/r['total']*100,'after':r['invested']+joint_shock(r['invested'],s,fx)} for s in range(-40,31,5) for fx in range(-20,21,5)}}
