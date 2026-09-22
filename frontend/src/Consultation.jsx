import { useState } from "react";
import { money, pct } from "./format";
export function ResearchLink({ c, id, label }) {
  const s = c.sources[id];
  return s ? (
    <a href={s.url} target="_blank" rel="noreferrer">
      {label || s.label} ↗ <small>{s.date}</small>
    </a>
  ) : null;
}
export function News({ r }) {
  const c = r.consultation;
  return (
    <section id="news" className="panel">
      <div className="section-heading">
        <h2>최근 뉴스, 보유 종목에 주는 의미</h2>
        <span>최근 7일 · 회사 발표 / 공시</span>
      </div>
      <div className="news-grid">
        {c.news
          .filter((n) => n.recent)
          .map((n) => (
            <article key={n.source}>
              <span className="eyebrow">
                {n.code} · {n.date}
              </span>
              <h3>{n.title}</h3>
              <p>{n.summary}</p>
              <p className="news-impact">{n.impact}</p>
              <ResearchLink c={c} id={n.source} label="발표 원문" />
            </article>
          ))}
      </div>
      {!c.news.some((n) => n.recent) && (
        <p>이 조사에 포함할 최근 7일 중요 뉴스를 확인하지 못했습니다.</p>
      )}
    </section>
  );
}
export function StockResearch({ r }) {
  const c = r.consultation;
  const [selected, setSelected] = useState(c.cards[0]?.security_id);
  return (
    <section id="stocks" className="panel stock-research">
      <div className="section-heading">
        <h2>종목별 기업 분석</h2>
        <span>실적 → 재무 해석 → 조건별 전망</span>
      </div>
      <div className="stock-tabs" role="tablist" aria-label="분석할 보유 종목">
        {c.cards.map((h) => (
          <button
            key={h.security_id}
            id={`tab-${h.security_id}`}
            role="tab"
            aria-selected={selected === h.security_id}
            aria-controls={`stock-${h.security_id}`}
            onClick={() => setSelected(h.security_id)}
          >
            {h.code}
            <small>{h.name}</small>
          </button>
        ))}
      </div>
      {c.cards.map((h) => {
        const b = h.research;
        return (
          <article
            key={h.security_id}
            id={`stock-${h.security_id}`}
            role="tabpanel"
            aria-labelledby={`tab-${h.security_id}`}
            hidden={selected !== h.security_id}
            className={`stock-detail ${selected === h.security_id ? "selected" : ""}`}
          >
            <div className="stock-title">
              <div>
                <span>
                  {h.code} · {h.sector}
                </span>
                <h3>{b?.title || "공식 자료 조사 필요"}</h3>
                <p>
                  {b?.thesis ||
                    "Codex가 이 종목을 조사하면 기업 분석이 표시됩니다."}
                </p>
              </div>
              <div className="position-note">
                <span>보유 평가액</span>
                <strong>{money(h.value)}</strong>
                <small>주식 내 {pct(h.equity_weight)}</small>
              </div>
            </div>
            {!b && h.research_state === 'unresolved' && <div className="notice"><b>조사 완료 · 미확인</b><p>{h.unresolved_reason}</p>{h.checked_sources.map(id => <ResearchLink key={id} c={c} id={id} />)}</div>}
            {b && (
              <>
                <div className="fact-strip">
                  {b.facts.map((f) => (
                    <div key={f.label}>
                      <span>{f.label}</span>
                      <strong>{f.value}</strong>
                      <small>{f.context}</small>
                    </div>
                  ))}
                </div>
                <div className="source-links">
                  {b.sources.map((id) => (
                    <ResearchLink key={id} c={c} id={id} />
                  ))}
                </div>
                <h3>재무제표에서 읽는 체력</h3>
                <div className="table-wrap">
                  <table className="financial-table">
                    <thead>
                      <tr>
                        <th>핵심 지표 / 기간</th>
                        <th>금액·비율</th>
                        <th>전년 동기 변화</th>
                        <th>근거</th>
                      </tr>
                    </thead>
                    <tbody>
                      {b.financials.rows.map((f, i) => (
                        <tr key={i}>
                          <td>
                            <strong>{f.label}</strong>
                            <small>{f.period}</small>
                          </td>
                          <td>
                            {f.value == null
                              ? "미확인"
                              : f.value.toLocaleString("ko-KR", {
                                  maximumFractionDigits: 2,
                                })}{" "}
                            {f.value != null && f.unit}
                            <small>{f.missing_reason}</small>
                          </td>
                          <td>
                            {f.yoy == null
                              ? "—"
                              : `${f.yoy > 0 ? "+" : ""}${f.yoy.toFixed(1)}%`}
                          </td>
                          <td>
                            <ResearchLink c={c} id={f.source} label="원문" />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="financial-takeaway">
                  <b>재무 해석</b>
                  <p>{b.financials.analysis}</p>
                  {b.financials.simple_fcf != null && (
                    <small>
                      단순 잉여현금 {b.financials.simple_fcf.toLocaleString()}{" "}
                      {b.financials.fcf_unit} = 영업현금 − 표의 설비투자 ·
                      회사별 공시 FCF 정의와 다를 수 있음
                    </small>
                  )}
                </div>
                <p className="scenario-caption">
                  조건별 전망 · Codex 해석 · 확률·목표주가를 제시하지 않음
                </p>
                <div className="outlook-grid">
                  {[
                    ["기본 전망", "base"],
                    ["기대가 강화되는 조건", "up"],
                    ["판단을 낮출 조건", "down"],
                  ].map(([title, key]) => (
                    <div key={key}>
                      <h4>{title}</h4>
                      <p>{b[key]}</p>
                    </div>
                  ))}
                </div>
                <div className="consultant-note">
                  <b>보유 관점의 해석</b>
                  <p>{b.decision}</p>
                  <p>
                    <strong>다음 확인</strong> {b.watch}
                  </p>
                </div>
                {!b.news.length && <p className="table-note">{b.news_note}</p>}
              </>
            )}
          </article>
        );
      })}
    </section>
  );
}
export function SectorResearch({ r }) {
  const c = r.consultation;
  return (
    <section id="sectors" className="panel sector-research">
      <div className="section-heading">
        <h2>섹터를 연결해서 보는 전망</h2>
        <span>사업 기준 분류</span>
      </div>
      <div className="sector-rows">
        {c.sectors.map((s) => (
          <article key={s.name}>
            <div>
              <h3>{s.name}</h3>
              <b>{pct(s.equity_weight)}</b>
              <small>주식 내 비중</small>
            </div>
            <div>
              <p>{s.outlook}</p>
              <small>확인 지표: {s.watch}</small>
              <div className="source-links">
                {s.sources.map((id) => (
                  <ResearchLink key={id} c={c} id={id} />
                ))}
              </div>
            </div>
          </article>
        ))}
      </div>
      {!c.sectors.length && <p>섹터 자료 조사 필요</p>}
      <p className="table-note">{c.theme_note}</p>
    </section>
  );
}
export function Monitoring({ r }) {
  const c = r.consultation;
  return (
    <section className="panel monitoring">
      <h2>다음 확인 일정</h2>
      {c.events.map((v, i) => (
        <article key={i}>
          <div>
            <strong>{v.date || "날짜 미확인"}</strong>
            <small>{v.status}</small>
          </div>
          <div>
            <h3>{v.title}</h3>
            <p>{v.watch}</p>
            <ResearchLink c={c} id={v.source} />
          </div>
        </article>
      ))}
      {!c.events.length && <p>공식 발표 일정을 아직 확인하지 못했습니다.</p>}
    </section>
  );
}
