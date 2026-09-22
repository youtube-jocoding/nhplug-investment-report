import { useState } from "react";
import { Check, ArrowUpRight, ChevronDown } from "lucide-react";
import { money, pct, colors } from "./format";
export function Metrics({ r }) {
  return (
    <section className="metrics" aria-label="자산 핵심 지표">
      {[
        ["분석 대상 자산", money(r.total), ""],
        [
          "평가손익",
          (r.pnl > 0 ? "+" : "") + money(r.pnl),
          r.pnl < 0 ? "negative" : "positive",
        ],
        [
          r.top_sector ? `${r.top_sector.name} 비중` : "업종 비중",
          r.top_sector ? pct(r.top_sector.weight) : "미확인",
          "",
        ],
        ["조회 예수금 (원화)", money(r.snapshot.cash), ""],
      ].map(([label, value, cl]) => (
        <div key={label}>
          <p>{label}</p>
          <strong className={cl}>{value}</strong>
        </div>
      ))}
    </section>
  );
}
export function Allocation({ r }) {
  return (
    <section className="panel allocation">
      <h2>보유 자산의 구성</h2>
      <div className="stack" aria-label="자산 구성 비중">
        {r.allocation.map((g, i) => (
          <div
            key={g.name}
            title={`${g.name} ${pct(g.weight)}`}
            style={{
              width: `${Math.max(0, g.weight)}%`,
              background: colors[i % colors.length],
            }}
          />
        ))}
      </div>
      <ul>
        {r.allocation.map((g, i) => (
          <li key={g.name}>
            <span>
              <i style={{ background: colors[i % colors.length] }} />
              {g.name}
            </span>
            <b>{pct(g.weight)}</b>
          </li>
        ))}
      </ul>
      <small>
        분모: 보유금액 + 조회 범위의 예수금
        <br />
        사업 기준 분석용 분류 · ETF 내부 중복 노출 미반영
      </small>
    </section>
  );
}
export function Holdings({ r }) {
  return (
    <section className="panel holdings">
      <div className="section-heading">
        <h2>보유 자산 자세히 보기</h2>
        <span>금액 단위 원 · 현금 제외</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>종목</th>
              <th>평가금액</th>
              <th>비중</th>
              <th>평가손익</th>
            </tr>
          </thead>
          <tbody>
            {r.snapshot.holdings.map((h, i) => (
              <tr key={h.code + "-" + i}>
                <td>
                  <strong>{h.name}</strong>
                  <small>
                    {h.code} · {h.sector}
                  </small>
                </td>
                <td>{money(h.value)}</td>
                <td>
                  <span
                    className="weight-line"
                    style={{ width: `${Math.min(h.weight, 100)}px` }}
                  />
                  {pct(h.weight)}
                </td>
                <td className={h.pnl < 0 ? "negative" : "positive"}>
                  {h.pnl > 0 ? "+" : ""}
                  {money(h.pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="table-note">
        보유 주식 매수금액 대비 미실현 손익률{" "}
        {r.unrealized_return == null ? "미확인" : pct(r.unrealized_return)} ·
        기간 수익률과 다릅니다.
      </p>
    </section>
  );
}
export function Evidence({ r }) {
  return (
    <section className="evidence">
      <details>
        <summary>
          출처와 계산 근거 확인 <ChevronDown size={16} />
        </summary>
        <div>
          <p>{r.method}</p>
          <p>
            비중 = 종목 평가금액 ÷ (보유 종목 평가금액 합 + 원화 예수금). 하락
            영향 = 해당 평가금액 × 가정한 가격 변화율.
          </p>
          {r.snapshot.sources.map((s) => (
            <p key={s.label}>
              {s.url ? (
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.label}
                  <ArrowUpRight size={14} />
                </a>
              ) : (
                s.label
              )}{" "}
              · {s.fields}
            </p>
          ))}
          {r.warnings.concat(r.limitations).map((t) => (
            <p key={t}>{t}</p>
          ))}
        </div>
      </details>
      <p>
        개인 확인용 리포트이며 투자 판단을 대신하지 않습니다.
        <br />
        Namuh PLUG의 데이터를 활용해 별도로 만든 데모입니다. NH의 완성형 리포트
        서비스가 아닙니다.
      </p>
    </section>
  );
}
