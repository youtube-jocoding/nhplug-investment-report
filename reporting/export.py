"""A short newsletter and a separately linked, complete research report."""
from html import escape as e
from email.message import EmailMessage
from pathlib import Path
import json,os
from .engine import won

DISCLAIMER='개인 확인용 리포트 · 투자 판단을 대신하지 않음 · 특정 종목 추천·수익 보장 아님'

def subject_for(day):
    from datetime import date
    d=date.fromisoformat(day)
    return f'내 투자 브리핑 | {d.month}월 {d.day}일'

def link(c,key,label=None):
    s=c['sources'][key]
    return f'<a href="{e(s["url"],quote=True)}" target="_blank" rel="noreferrer">{e(label or s["label"])} ↗</a>'

def shell(title,body,width=720):
    # Inline styles on the outer table survive common Gmail sanitizers.
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title><style>body{{margin:0;background:#f3f5f5;color:#183044;font:15px/1.7 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif}}h1{{font-size:28px;line-height:1.4}}h2{{font-size:19px;margin-top:28px}}h3{{font-size:17px}}a{{color:#147c65}}.meta,small{{color:#61717c;font-size:12px}}.verdict{{background:#edf5f1;padding:20px;border-left:3px solid #147c65}}table.data{{width:100%;border-collapse:collapse;font-size:14px}}.data td,.data th{{padding:10px 5px;border-bottom:1px solid #e1e7eb;text-align:left}}.data small{{display:block}}.tag{{font-size:11px;color:#147c65;letter-spacing:1px}}article{{padding:14px 0;border-bottom:1px solid #e1e7eb}}p{{margin:9px 0}}@media(max-width:600px){{.outer{{padding:20px!important}}h1{{font-size:24px}}}}@media print{{h2,h3{{break-after:avoid}}}}</style></head><body><table role="presentation" style="width:100%;border-collapse:collapse"><tr><td><table role="presentation" style="width:100%;max-width:{width}px;margin:0 auto;background:white;color:#183044;font:15px/1.7 -apple-system,BlinkMacSystemFont,Arial,sans-serif"><tr><td class="outer" style="padding:32px">{body}</td></tr></table></td></tr></table></body></html>'''

def newsletter(r,detail_url=None,attachment=False):
    c=r['consultation'];s=r['snapshot']
    prefix='가상 예시 · ' if s['mode']=='demo' else ''
    out=[f'<p class="tag" style="color:#147c65;font-size:12px">PORTFOLIO BRIEF · {e(c["as_of"] or "조사 대기")}</p><h1 style="font-size:27px;margin:12px 0">오늘의 포트폴리오</h1><p class="meta">{prefix}조회 {e(s["fetched_at"][:16].replace("T"," "))} KST · {e(s.get("market","kr").upper())}</p>',f'<p><strong>분석 자산 {won(r["total"])}</strong> &nbsp;·&nbsp; 미실현 손익 {won(r["pnl"])}</p>',f'<div class="verdict" style="background:#edf5f1;padding:18px;border-left:3px solid #147c65"><strong>{e(c["headline"])}</strong><p>{e(c["summary"])}</p></div>','<h2>보유 종목, 한 줄씩</h2><table class="data" role="presentation">']
    for h in c['cards'][:6]:
        b=h['research'];brief=b.get('brief',b['title']) if b else ('미확인 · '+h['unresolved_reason'] if h.get('unresolved_reason') else '공식 자료 조사 필요')
        source=link(c,b['sources'][0],'실적 원문') if b else ''
        out.append(f'<tr><td style="padding:10px 0;border-bottom:1px solid #e1e7eb;vertical-align:top;min-width:70px"><b>{e(h["code"])}</b><small style="display:block;color:#61717c">{h["equity_weight"]:.1f}%</small></td><td style="padding:10px 8px;border-bottom:1px solid #e1e7eb">{e(brief)} <small>{source}</small></td></tr>')
    out.append('</table><p class="meta">비중은 주식 평가액 기준 · 실적 기간은 원문/상세 리포트에 표시</p>')
    if len(c['cards'])>6:out.append(f'<p>외 {len(c["cards"])-6}종목은 상세 리포트에 수록했습니다.</p>')
    recent=[n for n in c['news'] if n['recent']][:2]
    out.append('<h2>체크할 뉴스</h2>')
    for n in recent:out.append(f'<p><b>{e(n["code"])} · {link(c,n["source"],n["title"])}</b> <small>{e(n["date"][5:])}</small><br>{e(n["impact"])}</p>')
    if not recent:out.append('<p>최근 7일 범위에서 추가할 중요 뉴스를 확인하지 못했습니다.</p>')
    if c['events']:
        v=c['events'][0];out.append(f'<h2>다음 확인</h2><p><b>{e(v.get("date") or "날짜 미확인")} · {e(v["title"])}</b><br>{e(v["watch"])} · {link(c,v["source"],"일정 원문")}</p>')
    if detail_url:out.append(f'<p style="margin:26px 0"><a style="background:#173247;color:white;padding:12px 18px;text-decoration:none;border-radius:4px;display:inline-block" href="{e(detail_url,quote=True)}">재무표·전망 상세 리포트 열기 ↗</a></p>')
    if attachment:out.append('<p><b>상세 분석은 첨부 report.html에 담았습니다.</b><br><small>다운로드해 브라우저로 열면 종목별 재무표·전망·원문 링크를 볼 수 있습니다.</small></p>')
    if c['stale']:out.append(f'<p class="meta">리서치 확인일 {e(c["as_of"] or "없음")} · 오늘 자료 재확인 필요</p>')
    out.append(f'<p style="margin-top:24px;font-size:11px;color:#71818c">{DISCLAIMER}<br>PLUG 데이터로 별도 제작한 리포트이며 NH의 완성형 서비스가 아닙니다.</p>')
    return shell('오늘의 포트폴리오 · 뉴스레터',''.join(out),680)

def html_report(r):
    c=r['consultation'];s=r['snapshot']
    out=[f'<p class="tag">PORTFOLIO RESEARCH · {e(c["as_of"] or "조사 대기")}</p><h1>포트폴리오 분석 리포트</h1><p class="meta">{e(s["account_label"])} · {e(s["scope"])}<br>잔고 조회 {e(s["fetched_at"])} · 기업 자료 확인 {e(c["as_of"] or "미확인")}</p><h2>{e(c["headline"])}</h2><p>{e(c["summary"])}</p><p>분석 자산 {won(r["total"])} · 주식 {won(r["invested"])} · 조회 예수금 {won(s["cash"])}</p>']
    for h in c['cards']:
        out.append(f'<article id="{e(h["code"],quote=True)}"><h2>{e(h["code"])} · {e(h["name"])}</h2><p>평가액 {won(h["value"])} · 주식 내 {h["equity_weight"]:.1f}% · 총액의 {h["weight"]:.1f}%</p>')
        b=h['research']
        if not b:
            out.append('<p>'+e('조사 완료 · 미확인: '+h['unresolved_reason'] if h.get('unresolved_reason') else '공식 자료 조사 필요')+'</p>')
            out.extend(link(c,k) for k in h.get('checked_sources',[]))
            out.append('</article>');continue
        out.append(f'<h3>{e(b["title"])}</h3><p>{e(b["thesis"])}</p>')
        for f in b['facts']:out.append(f'<p><b>{e(f["label"])} {e(f["value"])}</b> · {e(f["context"])}</p>')
        out.append('<p>'+ ' · '.join(link(c,k) for k in b['sources'])+'</p><h3>재무제표 핵심</h3><table class="data"><tr><th>지표 / 기간</th><th>수치</th><th>전년 동기</th></tr>')
        fin=b['financials']
        for row in fin['rows']:
            val='미확인' if row.get('value') is None else f'{row["value"]:,.2f}'.rstrip('0').rstrip('.')
            change='—' if row.get('yoy') is None else f'{row["yoy"]:+.1f}%'
            out.append(f'<tr><td>{e(row["label"])}<small>{e(row["period"])} · {link(c,row["source"],"원문")}</small></td><td>{val} {e(row["unit"])}<small>{e(row.get("missing_reason",""))}</small></td><td>{change}</td></tr>')
        out.append('</table>')
        if fin.get('operating_margin') is not None:out.append(f'<p>계산한 영업이익률 {fin["operating_margin"]:.1f}% (영업이익 ÷ 매출)</p>')
        if fin.get('simple_fcf') is not None:out.append(f'<p>단순 잉여현금 {fin["simple_fcf"]:,.0f} {e(fin["fcf_unit"])} · {e(fin["fcf_period"])}<small> 영업현금 − 표의 설비투자. 회사별 공시 FCF와 정의가 다를 수 있습니다.</small></p>')
        out.append(f'<p><b>재무 해석</b> {e(fin.get("analysis","미확인"))}</p><h3>최근 뉴스와 의미</h3>')
        for n in b['news']:out.append(f'<p>{"최근 7일" if n.get("recent") else "과거 발표 · 배경 자료"} · {e(n["date"])} · {link(c,n["source"],n["title"])}<br>{e(n["summary"])}<br>{e(n["impact"])}</p>')
        if not b['news']:out.append(f'<p>{e(b.get("news_note","미확인"))}</p>')
        for title,key in [('기본 전망','base'),('기대가 강화되는 조건','up'),('판단을 낮출 조건','down'),('보유 관점의 해석','decision'),('다음 확인 지표','watch')]:out.append(f'<p><b>{title} · Codex 해석</b><br>{e(b[key])}</p>')
        out.append('</article>')
    out.append('<h2>섹터별 전망</h2>')
    for g in c['sectors']:out.append(f'<h3>{e(g["name"])} · 주식 내 {g["equity_weight"]:.1f}%</h3><p>{e(g["outlook"])}<br><b>확인 지표</b> {e(g["watch"])}</p><p>'+ ' · '.join(link(c,k) for k in g['sources'])+'</p>')
    out.append('<h2>다음 일정</h2>')
    for v in c['events']:out.append(f'<p>{e(v.get("date") or "날짜 미확인")} · {e(v["title"])} · {e(v["status"])}<br>{e(v["watch"])} · {link(c,v["source"])}</p>')
    out.extend(['<h2>출처와 분석 범위</h2>',f'<p>{e(c["valuation"])}</p>',*[f'<p>{link(c,k)} · {e(v["date"])}</p>' for k,v in c['sources'].items()],*[f'<p class="meta">{e(x)}</p>' for x in r['warnings']+r['limitations']],f'<p>{DISCLAIMER}</p>'])
    if not r['research_status']['allocation_ready']:out.append('<p>업종 분류가 모두 확인되지 않아 섹터 비중은 계산하지 않았습니다.</p>')
    if s['mode']=='demo':out.insert(0,'<p style="border:2px solid #b98018;padding:12px"><b>가상 예시 · 보유 금액과 손익은 실제 계좌가 아닙니다.</b></p>')
    return shell('포트폴리오 분석 리포트',''.join(out),920)

def markdown(r):
    c=r['consultation'];lines=['# 포트폴리오 분석',c['headline'],c['summary'],f'자료 확인: {c["as_of"]} / 잔고 조회: {r["snapshot"]["fetched_at"]}']
    for h in c['cards']:
        lines.append(f'## {h["code"]} · {h["name"]}')
        b=h['research']
        if not b:lines.append('공식 자료 조사 필요');continue
        lines.extend([b['thesis'],b['financials'].get('analysis','')])
        for key in ('base','up','down','watch'):lines.append(b[key])
        for k in b['sources']:
            s=c['sources'][k];lines.append(f'[{s["label"]} · {s["date"]}]({s["url"]})')
    return '\n\n'.join(lines+[DISCLAIMER])

def email_message(r):
    msg=EmailMessage();msg['Subject']=subject_for(r['consultation']['as_of']) if r['consultation']['as_of'] else '내 투자 브리핑'
    msg.set_content('포트폴리오 뉴스레터입니다. HTML 본문과 첨부 상세 리포트를 확인하세요.')
    msg.add_alternative(newsletter(r,attachment=True),subtype='html')
    msg.add_attachment(html_report(r).encode(),maintype='text',subtype='html',filename='report.html')
    return msg

def save_report(r,directory):
    directory=Path(directory);directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    artifacts={'report.json':json.dumps(r,ensure_ascii=False,indent=2),'report.md':markdown(r),'report.html':html_report(r),'newsletter.html':newsletter(r,detail_url='report.html'),'report.eml':email_message(r).as_string()}
    for name,content in artifacts.items():
        fd=os.open(directory/name,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(content)
