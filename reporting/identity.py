"""Exact instrument identities. Never infer a ticker from a company name."""
import re

SECTORS = {
    'semiconductors': '반도체', 'software': '소프트웨어·클라우드',
    'communication': '커뮤니케이션 서비스', 'hardware': 'IT 하드웨어',
    'financials': '금융', 'healthcare': '헬스케어', 'industrials': '산업재',
    'consumer_discretionary': '경기소비재', 'consumer_staples': '필수소비재',
    'energy': '에너지', 'materials': '소재', 'utilities': '유틸리티',
    'real_estate': '부동산', 'diversified_fund': '분산형 펀드·ETF',
    'other': '기타 확인 업종',
}
PRODUCTS = {'COMMON', 'ADR', 'PREFERRED', 'ETF', 'ETN', 'FUND', 'OTHER', 'UNKNOWN'}


def identity(market, exchange, code, product_type):
    parts = [str(x or 'UNKNOWN').strip().upper() for x in (market, exchange, code, product_type)]
    if any(not re.fullmatch(r'[A-Z0-9._-]{1,40}', x) for x in parts) or parts[0] not in ('US', 'KR') or parts[3] not in PRODUCTS:
        raise ValueError('시장·거래소·종목코드·상품 종류 식별자를 확인하세요.')
    return '|'.join(parts)


def holding_identity(h, market):
    code = str(h['code']).strip().upper()
    # The current balance endpoint doesn't establish exchange/product type.
    # Preserve explicit metadata when present, otherwise research must resolve it.
    exchange = h.get('exchange', 'UNKNOWN')
    product = h.get('product_type', 'UNKNOWN')
    return {'code': code, 'market': market.upper(), 'exchange': exchange.upper(), 'product_type': product.upper(),
            'security_id': identity(market, exchange, code, product)}


def instrument_key(h, market):
    return holding_identity(h, market)['security_id']


def research_for(h, data, market):
    if data.get('version') != 2: return None
    b = data.get('stocks', {}).get(instrument_key(h, market))
    return b if b and b.get('status') == 'verified' else None


def coverage(snapshot, data):
    keys = {instrument_key(h, snapshot.get('market', 'kr')) for h in snapshot['holdings']}
    stocks = data.get('stocks', {}) if data.get('version') == 2 else {}
    states = [stocks.get(k, {}).get('status', 'pending') for k in keys]
    exact = keys == set(stocks)
    verified = states.count('verified')
    unresolved = states.count('unresolved')
    return {'verified': verified, 'unresolved': unresolved, 'pending': len(keys) - verified - unresolved,
            'total': len(keys), 'exact': exact, 'allocation_ready': exact and verified == len(keys),
            'final_ready': exact and 'pending' not in states}


def require_complete(snapshot, data):
    from .research_store import validate
    validate(data)
    c = coverage(snapshot, data)
    if not c['exact']: raise ValueError('리서치 종목과 실제 보유 종목 집합이 다릅니다. 현재 보유 종목만 빠짐없이 조사하세요.')
    if not c['final_ready']: raise ValueError('조사 대기 종목이 있습니다. 검증 완료 또는 출처·사유가 있는 미확인 상태로 마무리하세요.')
    return c
