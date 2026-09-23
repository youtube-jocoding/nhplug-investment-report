"""Portfolio arithmetic only. All business research is a separate, dated input."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from copy import deepcopy
import json
from .paths import ROOT
KST=timezone(timedelta(hours=9))

def number(value,label='금액',minimum=0,maximum=10**15):
    if value is None or isinstance(value,bool):raise ValueError(f'{label}: 숫자가 필요합니다.')
    try:n=Decimal(str(value).replace(',','').strip())
    except InvalidOperation:raise ValueError(f'{label}: 숫자 형식이 아닙니다.') from None
    if not n.is_finite() or n<minimum or n>maximum:raise ValueError(f'{label}: 허용 범위를 벗어났습니다.')
    return float(n)

def won(value):
    if value is None:return '미확인'
    return f'{value:,.0f}원'

def demo_snapshot():
    return json.loads((ROOT/'examples/portfolio.json').read_text(encoding='utf-8'))

def joint_shock(value,stock_pct,fx_pct):
    return value*((1+stock_pct/100)*(1+fx_pct/100)-1)

def analyze(snapshot,research=None):
    from .research_store import load
    from .research import enrich,build_consultation
    research=research if research is not None else load(snapshot['mode']=='demo')
    s=enrich(deepcopy(snapshot),research)
    cash=number(s['cash'],'예수금',-10**15)
    groups={};securities={}
    for h in s['holdings']:
        h['value']=number(h['value'],'평가금액')
        for k in ('cost','pnl'):
            h[k]=None if h.get(k) is None else number(h[k],k,-10**15 if k=='pnl' else 0)
    invested=sum(h['value'] for h in s['holdings']);total=invested+cash
    if total<=0:raise ValueError('분석 대상 자산이 0 이하입니다.')
    for h in s['holdings']:
        h['weight']=h['value']/total*100
        sector=h.get('sector') or '분류 미확인'
        groups[sector]=groups.get(sector,0)+h['value']
        bucket=securities.setdefault(h['code'],{'name':h['name'],'value':0})
        bucket['value']+=h['value']
    allocation=sorted([{'name':k,'value':v,'weight':v/total*100} for k,v in groups.items()],key=lambda x:-x['value'])
    top_sector=next((g for g in allocation if g['name']!='분류 미확인'),None)
    allocation.append({'name':'현금','value':cash,'weight':cash/total*100})
    top=max(securities.values(),key=lambda h:h['value'],default={'name':'보유 없음','value':0})
    top['weight']=top['value']/total*100
    pnl=sum(h['pnl'] for h in s['holdings']) if all(h['pnl'] is not None for h in s['holdings']) else None
    cost=sum(h['cost'] for h in s['holdings']) if all(h['cost'] is not None for h in s['holdings']) else None
    r={'snapshot':s,'total':total,'invested':invested,'pnl':pnl,'cost':cost,'allocation':allocation,'top_sector':top_sector,'top_position':top,'unrealized_return':pnl/cost*100 if cost and pnl is not None else None,'warnings':s.get('warnings',[]),'limitations':['선택한 계좌·시장의 부분 자산이며 부채를 차감한 전체 순자산이 아닙니다.','평가손익은 미실현 손익이며 기간 수익률이 아닙니다. 세금·수수료·배당·실현손익은 미반영입니다.','사업 전망은 조건부 해석입니다. 목표주가·매매 추천·수익 보장을 제공하지 않습니다.']}
    r['consultation']=build_consultation(r,research)
    r['method']='PLUG 잔고 수치 검산 + Codex의 출처 기반 기업 분석. 계좌 조회시각과 리서치 확인일을 구분합니다.'
    return r
