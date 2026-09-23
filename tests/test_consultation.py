from copy import deepcopy
from datetime import date
import pytest
from reporting.provider import normalize_us,GLOBAL_BALANCE,ALLOWED
from reporting.engine import analyze,joint_shock
from reporting.research_store import load
from reporting.export import html_report,markdown


def sample(code='NVDA'):
    row={'iem_cd':code,'iem_nm':'검증 종목','cur_cd':'USD','krw_eal_amt':140000,'krw_abk_amt1':130000,'krw_eal_pls_amt':10000,'fc_eal_amt':100,'fc_abk_amt':95,'cns_bse_bnc_qty':1,'tdt_sby_bse_xcg_rt':1400,'act_no':'do-not-export'}
    summary={'eal_amt_sum':140000,'abk_amt':130000,'eal_pls_sum_amt':10000,'krw_dca':70000,'fc_dca':50}
    return [row],summary


def report(code='NVDA'):
    rows,summary=sample(code)
    data=load(True);data['stocks']={k:v for k,v in data['stocks'].items() if k=='US|UNKNOWN|'+code+'|UNKNOWN'}
    return analyze(normalize_us(rows,summary,'운영 ****0000','live','2026-09-23T00:00:00+09:00'),data)


def test_us_values_remain_krw_and_cash_is_counted_once():
    r=report()
    assert r['invested']==140000 and r['total']==210000 and r['pnl']==10000
    assert r['snapshot']['withdrawable'] is None
    assert 'do-not-export' not in str(r)
    assert r['top_sector']['name']=='반도체'


@pytest.mark.parametrize('field',['eal_amt_sum','abk_amt','eal_pls_sum_amt'])
def test_us_inconsistent_totals_fail(field):
    rows,summary=sample();summary[field]+=100
    with pytest.raises(ValueError):normalize_us(rows,summary,'x','live','now')


def test_non_usd_rows_cannot_mix_with_us_analysis():
    rows,summary=sample();rows[0]['cur_cd']='JPY'
    with pytest.raises(ValueError):normalize_us(rows,summary,'x','live','now')




def test_compound_currency_loss_is_28_not_30_percent():
    assert joint_shock(1000000,-20,-10)==pytest.approx(-280000)
    r=report();s=r['consultation']['scenarios']['-20:-10']
    assert s['change']==pytest.approx(-39200)
    assert s['after']==pytest.approx(100800)




def test_unknown_stock_does_not_get_fabricated_research():
    r=report('UNKNOWN')
    assert r['consultation']['coverage']==0
    assert r['consultation']['cards'][0]['research'] is None
    assert r['top_sector'] is None




def test_same_ticker_lots_get_one_consultation_and_accurate_weight():
    rows,summary=sample();rows*=2
    for k in ('eal_amt_sum','abk_amt','eal_pls_sum_amt'):summary[k]*=2
    r=analyze(normalize_us(rows,summary,'x','live','now'))
    cards=r['consultation']['cards']
    assert len(cards)==1 and cards[0]['value']==280000
    assert cards[0]['equity_weight']==100


def test_both_exports_include_full_research_and_sources():
    r=report()
    for text in (html_report(r),markdown(r)):
        assert '다음' in text
        assert 'nvidianews.nvidia.com' in text
        assert '가상 비교' not in text
        assert '2026-08-26' in text
    assert GLOBAL_BALANCE in ALLOWED
    assert not any('/order/' in p for p in ALLOWED)
