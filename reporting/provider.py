"""PLUG read-only adapter; official SDK handles credentials, token cache and throttle."""
import os
import json
import secrets
from datetime import datetime
from urllib.parse import urlparse
from .engine import KST, number

BALANCE = '/krstock/inquiry/v1/balance'
ACCOUNTS = '/n2/acctinfo'
GLOBAL_BALANCE = '/gbstock/inquiry/v1/balance'
ALLOWED = {ACCOUNTS, BALANCE, GLOBAL_BALANCE}


def safe_connection_error(error):
    """Map recognized status/code only; never echo SDK messages or raw responses."""
    code=getattr(error,'code',None)
    raw=getattr(error,'raw',None)
    if isinstance(raw,str):
        try:raw=json.loads(raw)
        except (ValueError,TypeError):raw=None
    if isinstance(raw,dict):code=code or raw.get('error_code')
    if code=='IGW40031':
        return 'API 키 인증 실패 (IGW40031): PLUG가 현재 앱키를 유효하지 않은 키로 응답했습니다. 발급 브랜드와 현재 사용 가능한 앱키·앱시크릿을 확인한 뒤 아래에서 다시 연결하세요.'
    if getattr(error,'status',None)==429:
        return 'PLUG 조회 한도를 초과했습니다. 잠시 후 다시 조회하세요.'
    if getattr(error,'category',None)=='network':
        return 'PLUG 서버에 연결하지 못했습니다. 네트워크와 서버 상태를 확인하세요.'
    if getattr(error,'category',None)=='auth':
        return 'PLUG 인증에 실패했습니다. 로컬 앱키·앱시크릿과 발급 브랜드를 확인하세요.'
    if getattr(error,'status',None)==403:
        return 'PLUG 접근이 거절됐습니다. API 이용 권한과 등록된 접속 조건을 확인하세요.'
    return 'PLUG 조회에 실패했습니다. 로컬 설정과 API 이용 상태를 확인하세요.'


def message(data):
    m = data.get('message') or {}
    if isinstance(m, list):
        m = m[-1] if m else {}
    if not isinstance(m, dict):
        m = {}
    return str(data.get('rsp_msg') or m.get('usr_msg') or ''), str(data.get('rsp_cd') or m.get('msg_code') or '')


def check_business(data):
    if not isinstance(data, dict):
        raise ValueError('PLUG 응답 형식을 확인할 수 없습니다.')
    text, _ = message(data)
    if any(word in text for word in ('실패','오류','불가','잘못','입력하','만료','권한','유효하지')):
        raise ValueError('PLUG가 조회 오류를 반환했습니다. 자격증명·계좌·이용 권한을 확인하세요.')


def collect_pages(fetch, path, payload):
    """Never return a partial report on broken/repeated continuation tokens."""
    rows, summary, seen = [], None, set()
    cts = flag = None
    for _ in range(100):
        data, meta = fetch(path, payload, cts=cts, cts_flag=flag, want_meta=True)
        check_business(data)
        block = data.get('Output_1')
        if block is not None and not isinstance(block,list):
            raise ValueError('잔고 목록 형식이 공식 명세와 다릅니다.')
        rows.extend(block or [])
        if isinstance(data.get('Output_0'),dict):
            summary = data['Output_0']
        _, code = message(data)
        more = meta.has_next or (meta.cts_flag or '').upper() == 'Y' or (code in ('00165','00218') and (meta.cts_flag or '').upper() != 'N')
        if not more:
            # Totals are documented to be supplied after ALL positions have been retrieved.
            if not isinstance(data.get('Output_0'),dict):
                raise ValueError('마지막 페이지의 집계가 없어 전체 잔고를 확정하지 않았습니다.')
            return rows, data['Output_0']
        if not meta.cts or meta.cts in seen:
            raise ValueError('연속조회 키가 없거나 반복되어 불완전한 리포트를 중단했습니다.')
        seen.add(meta.cts)
        cts, flag = meta.cts, meta.cts_flag or 'Y'
    raise ValueError('연속조회 한도를 초과했습니다. 일부 잔고를 전체로 표시하지 않습니다.')


def normalize(rows, summary, label, mode, fetched_at):
    holdings=[]
    for h in rows:
        if not isinstance(h,dict) or not h.get('iem_cd') or not h.get('iem_nm'):
            raise ValueError('보유 종목 식별 정보가 누락되었습니다.')
        holdings.append({'code':str(h['iem_cd']).strip(),'name':str(h['iem_nm']).strip(),'value':number(h.get('eal_amt'),'평가금액'),'cost':None if h.get('byn_amt') in (None,'') else number(h['byn_amt'],'매수금액'),'pnl':None if h.get('eal_pls_amt') in (None,'') else number(h['eal_pls_amt'],'평가손익',-10**15),'sector':'분류 미확인','sector_source':'잔고 API만으로 업종 확정 불가','kind':str(h.get('pdt_tp_nm') or '미확인')})
    actual = sum(h['value'] for h in holdings)
    expected = number(summary.get('tot_eal_amt'),'총평가금액')
    if abs(actual-expected)>max(1,len(holdings)):
        raise ValueError('보유 종목 합계와 공식 총평가금액이 일치하지 않아 리포트를 중단했습니다.')
    warnings=['업종 마스터·ETF 구성 자료가 연결되지 않아 실제 계좌의 업종 비중은 미확인으로 표시합니다.','API는 잔고의 개별 시세 기준시각을 제공하지 않습니다. 조회 완료시각을 별도 표시합니다.']
    liabilities = [k for k in ('rba','lon_amt','fnn_amt','ny_rdp_amt') if summary.get(k) not in (None,'') and number(summary[k],k,-10**15)!=0]
    if liabilities:
        warnings.append('미수·대출 관련 잔액이 있습니다. 이 리포트는 부채를 차감한 순자산 분석이 아닙니다.')
    return {'mode':mode,'as_of':None,'fetched_at':fetched_at,'account_label':label,'scope':'선택한 한 계좌의 국내주식 잔고와 원화 예수금','cash':number(summary.get('dca'),'예수금',-10**15),'withdrawable':None if summary.get('drn_pbl_amt') in (None,'') else number(summary['drn_pbl_amt'],'출금가능금액'),'holdings':holdings,'warnings':warnings,'sources':[{'label':'NH PLUG 국내주식 잔고 API','url':'https://www.nhplug.com/openapi-docs/krstock/openapi.json','fields':'Output_0: dca, drn_pbl_amt, tot_eal_amt / Output_1: iem_cd, iem_nm, eal_amt, byn_amt, eal_pls_amt'}]}


class PlugReader:
    def __init__(self, credential_path=None):
        self.credential_path = credential_path
        self.accounts = {}
        self._call = None

    def setup(self):
        if self._call:
            return
        from nhplug import call  # official SDK loads local .env without printing values
        from .credentials import load_saved, CREDENTIAL_PATH
        if self.credential_path is not False:
            saved=load_saved(self.credential_path or CREDENTIAL_PATH)
            if saved:os.environ.update(saved)
        for var in ('NHPLUG_BASE_URL','NHPLUG_AUTH_URL'):
            val = os.environ.get(var,'https://api.nhplug.com:8443')
            u = urlparse(val)
            if u.scheme != 'https' or u.hostname not in {'api.nhplug.com','moapi.nhplug.com','api.n2plug.com','moapi.n2plug.com'} or u.port != 8443 or u.path not in ('','/') or u.query or u.fragment or u.username:
                raise ValueError('공식 PLUG HTTPS 주소만 사용할 수 있습니다.')
        auth = os.environ.get('NHPLUG_AUTH_URL','https://api.nhplug.com:8443')
        if urlparse(auth).hostname.startswith('moapi'):
            raise ValueError('인증은 운영 도메인을 사용해야 합니다.')
        self.auth_url = auth
        self._call = call

    def fetch(self,path,payload,**kwargs):
        if path not in ALLOWED:
            raise ValueError('이 앱은 계좌 목록과 잔고 조회만 허용합니다.')
        self.setup()
        try:
            return self._call(path,payload,**kwargs)
        except Exception as error:
            raise ValueError(safe_connection_error(error)) from None

    def list_accounts(self):
        self.setup()
        before=os.environ.get('NHPLUG_BASE_URL')
        os.environ['NHPLUG_BASE_URL']=self.auth_url
        try:
            data,meta=self.fetch(ACCOUNTS,{},want_meta=True)
        finally:
            if before is None: os.environ.pop('NHPLUG_BASE_URL',None)
            else: os.environ['NHPLUG_BASE_URL']=before
        check_business(data)
        if meta.has_next or (meta.cts_flag or '').upper()=='Y':
            raise ValueError('계좌 목록 연속조회가 필요합니다. 일부 목록에서 자동 선택하지 않습니다.')
        rows=data.get('Output_0')
        if not isinstance(rows,list) or not rows:
            raise ValueError('조회 가능한 계좌 목록이 없습니다. API 신청 상태를 확인하세요.')
        self.accounts={}
        result=[]
        for row in rows:
            raw=str(row.get('acct_no') or '').strip()
            kind=str(row.get('acct_type') or '').strip()
            if not raw or kind not in ('01','02','03'): continue
            ref=secrets.token_urlsafe(18)
            label=('모의' if kind=='03' else '운영')+' 계좌 · ****'+raw[-4:]
            self.accounts[ref]={'raw':raw,'kind':kind,'label':label}
            result.append({'ref':ref,'label':label})
        return result

    def balance(self,ref,market='kr'):
        if market not in ('kr','us'):
            raise ValueError('지원하는 조회 시장은 국내 또는 미국입니다.')
        if ref not in self.accounts:
            raise ValueError('계좌 목록을 조회한 뒤 분석할 계좌를 직접 선택하세요.')
        account=self.accounts[ref]
        self.setup()
        brand='n2plug' if 'n2plug.com' in self.auth_url else 'nhplug'
        host='moapi' if account['kind']=='03' else 'api'
        before=os.environ.get('NHPLUG_BASE_URL')
        os.environ['NHPLUG_BASE_URL']=f'https://{host}.{brand}.com:8443'
        try:
            if market=='us':
                rows,summary=collect_pages(self.fetch,GLOBAL_BALANCE,{'act_no':account['raw'],'qut_iqr_dit_cd':'9','fc_sec_trd_nat_cd':'200','cur_cd':'KRW','xns_dit_cd':'0'})
            else:
                rows,summary=collect_pages(self.fetch,BALANCE,{'act_no':account['raw'],'bnc_bse_cd':'5','ltg_aot_dit_cd':'9','aet_bse':'2','qut_dit_cd':'UNT','aly_qut_cd':'2'})
        finally:
            if before is None: os.environ.pop('NHPLUG_BASE_URL',None)
            else: os.environ['NHPLUG_BASE_URL']=before
        normalizer=normalize_us if market=='us' else normalize
        result=normalizer(rows,summary,account['label'],'mock' if host=='moapi' else 'live',datetime.now(KST).isoformat())
        result['market']=market
        return result


def normalize_us(rows,summary,label,mode,fetched_at):
    holdings=[]
    optional=lambda row,key,label,minimum=0: None if row.get(key) in (None,'') else number(row[key],label,minimum)
    for h in rows:
        if not isinstance(h,dict) or not h.get('iem_cd') or not h.get('iem_nm'):
            raise ValueError('해외 보유 종목 식별 정보가 누락되었습니다.')
        if h.get('cur_cd')!='USD':
            raise ValueError('미국 조회에 다른 통화가 섞여 있어 합산하지 않았습니다.')
        holdings.append({'code':h['iem_cd'].strip(),'name':h['iem_nm'].strip(),
            'value':number(h.get('krw_eal_amt'),'원화평가금액'),
            'cost':optional(h,'krw_abk_amt1','원화장부금액'),
            'pnl':optional(h,'krw_eal_pls_amt','원화평가손익',-10**15),
            'currency':'USD','quantity':optional(h,'cns_bse_bnc_qty','보유수량'),
            'native_value':optional(h,'fc_eal_amt','외화평가금액'),
            'native_cost':optional(h,'fc_abk_amt','외화장부금액'),
            'fx_rate':optional(h,'tdt_sby_bse_xcg_rt','매매기준환율'),
            'sector':'분류 미확인','sector_source':'공시 확인 전','kind':'미국 상장 증권'})
    expected=number(summary.get('eal_amt_sum'),'해외평가금액합계')
    if abs(sum(h['value'] for h in holdings)-expected)>max(1,len(holdings)):
        raise ValueError('해외 보유 종목 합계와 공식 집계가 일치하지 않습니다.')
    for field,summary_key in [('cost','abk_amt'),('pnl','eal_pls_sum_amt')]:
        if summary.get(summary_key) not in (None,'') and all(h[field] is not None for h in holdings):
            if abs(sum(h[field] for h in holdings)-number(summary[summary_key],summary_key,-10**15))>max(1,len(holdings)):
                raise ValueError('해외 매입금액 또는 손익의 합계가 공식 집계와 다릅니다.')
    cash=number(summary.get('krw_dca'),'해외조회 예수금 원화표시',-10**15)
    warnings=['미국주식 조회의 보유금액과 예수금만 분석합니다. 국내조회 예수금과 합산하지 않았습니다.',
        'API의 원화 평가액을 사용합니다. 조회 완료시각과 개별 시세 기준시각은 다르며 실시간 시세 여부는 확인되지 않습니다.',
        '해외조회 예수금은 출금가능금액이 아닙니다. 결제·환전·담보 조건은 별도 확인이 필요합니다.']
    return {'mode':mode,'market':'us','as_of':None,'fetched_at':fetched_at,'account_label':label,
        'scope':'선택한 계좌의 미국주식 + 해외조회 예수금(원화 표시)','cash':cash,'withdrawable':None,
        'cash_label':'해외조회 예수금 · 원화 표시','cash_native':optional(summary,'fc_dca','외화예수금',-10**15),
        'holdings':holdings,'warnings':warnings,
        'sources':[{'label':'NH PLUG 해외주식 잔고 API','url':'https://www.nhplug.com/openapi-docs/gbstock/openapi.json','fields':'미국 200 · KRW 전체 · 비용 미포함 / 종목 krw_eal_amt, krw_abk_amt1, krw_eal_pls_amt 합계 검증 / 예수금 krw_dca 1회 반영'}]}
