import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, CalendarDays, Pause, Play } from "lucide-react";
import { api } from "./api";
import "./archive.css";

const previewHeadlines = {
  "2026-09-25": "클라우드와 AI 반도체 성장, 현금 전환이 다음 확인점",
  "2026-09-24": "AI 인프라 투자는 지속, 전력과 투자비 회수 속도 점검",
};

function dateLabel(value) {
  const [, month, day] = value.split("-");
  return `${Number(month)}월 ${Number(day)}일`;
}

function sourceLink(source, label = "원문") {
  return (
    <a href={source.url} target="_blank" rel="noreferrer">
      {label} <ArrowUpRight size={13} />
    </a>
  );
}

function filmingEntries(entries) {
  if (!entries.length) return [];
  const byDate = Object.fromEntries(entries.map((entry) => [entry.date, entry]));
  const latest = entries[0];
  const realEntries = entries.map((entry) => ({ ...entry, preview: false }));
  const filmingWindow = latest.date <= "2026-09-25" && byDate["2026-09-23"];
  const previews = filmingWindow ? ["2026-09-25", "2026-09-24"]
    .filter((date) => !byDate[date])
    .map((date) => ({
      ...latest,
      date,
      headline: previewHeadlines[date] || latest.headline,
      preview: true,
    })) : [];
  return [...realEntries, ...previews].sort((a, b) => b.date.localeCompare(a.date));
}

function DateRail({ entries, selected, onSelect }) {
  return (
    <aside className="archive-rail" aria-label="일자별 리포트">
      {entries.map((entry) => (
        <button
          key={entry.date}
          className={selected === entry.date ? "archive-day selected" : "archive-day"}
          onClick={() => onSelect(entry.date)}
        >
          <span className="day-title">{dateLabel(entry.date)}</span>
          {entry.preview && <small>촬영 미리보기</small>}
          <p>{entry.headline}</p>
          <span className="ticker-row">
            {entry.stocks.map((stock) => <i key={stock.code}>{stock.code}</i>)}
          </span>
        </button>
      ))}
    </aside>
  );
}

function Report({ entry }) {
  const [ticker, setTicker] = useState(entry.stocks[0]?.code);
  useEffect(() => setTicker(entry.stocks[0]?.code), [entry.date, entry.stocks]);
  const selectedStock = entry.stocks.find((stock) => stock.code === ticker) || entry.stocks[0];
  return (
    <article className="archive-report">
      <header className="report-lead">
        <div className="report-date">
          {entry.date.replaceAll("-", ".")}
          {entry.preview && <span>촬영 시연용</span>}
        </div>
        <h1>{entry.headline}</h1>
        <p>{entry.summary}</p>
      </header>

      <section className="diagnosis">
        <h2>핵심 진단</h2>
        <ul>
          {entry.stocks.map((stock) => <li key={stock.code}>{stock.decision}</li>)}
        </ul>
      </section>

      <section className="one-lines">
        <h2>종목별 한 줄</h2>
        <div className="stock-lines">
          {entry.stocks.map((stock) => (
            <div key={stock.code}>
              <strong>{stock.code}</strong>
              <p>{stock.brief}</p>
              {sourceLink(stock.sources[0], "실적 원문")}
            </div>
          ))}
        </div>
      </section>

      <section className="archive-news">
        <h2>주요 뉴스</h2>
        <div className="archive-news-grid">
          {entry.news.slice(0, 2).map((item, index) => (
            <article key={`${item.code}-${item.title}`}>
              <span>0{index + 1}</span>
              <div>
                <strong>{item.code} · {item.title}</strong>
                <p>{item.impact}</p>
                {sourceLink(item.source, `${item.date} 원문`)}
              </div>
            </article>
          ))}
        </div>
      </section>

      {selectedStock && (
        <section className="deep-dive">
          <div className="section-title">
            <h2>주요 종목 심층 분석</h2>
            <nav aria-label="종목 선택">
              {entry.stocks.map((stock) => (
                <button
                  key={stock.code}
                  className={ticker === stock.code ? "active" : ""}
                  onClick={() => setTicker(stock.code)}
                >{stock.code}</button>
              ))}
            </nav>
          </div>
          <div className="archive-stock-detail">
            <div className="stock-story">
              <h3>{selectedStock.code}</h3>
              <h4>{selectedStock.title}</h4>
              <p>{selectedStock.thesis}</p>
              <dl>
                <div><dt>기본 전망</dt><dd>{selectedStock.base}</dd></div>
                <div><dt>강화 조건</dt><dd>{selectedStock.up}</dd></div>
                <div><dt>위험 조건</dt><dd>{selectedStock.down}</dd></div>
              </dl>
            </div>
            <div className="archive-financial-table">
              <h3>최근 재무 핵심</h3>
              <table>
                <thead><tr><th>지표</th><th>기간</th><th>수치</th><th>원문</th></tr></thead>
                <tbody>
                  {selectedStock.financials.map((row) => (
                    <tr key={`${row.id}-${row.period}`}>
                      <td>{row.label}</td><td>{row.period}</td>
                      <td>{row.value == null ? "미확인" : `${row.value.toLocaleString("ko-KR")} ${row.unit}`}</td>
                      <td>{sourceLink(row.source)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p>{selectedStock.financial_analysis}</p>
            </div>
          </div>
          <div className="watch-line"><strong>다음 확인 지표</strong><p>{selectedStock.watch}</p></div>
        </section>
      )}

      <section className="next-event">
        <h2>다음 일정</h2>
        {entry.events.length ? entry.events.slice(0, 1).map((event) => (
          <div key={`${event.date}-${event.title}`}>
            <time>{event.date || "날짜 미확인"}</time>
            <strong>{event.title}</strong><p>{event.watch}</p>
            {sourceLink(event.source, "일정 원문")}
          </div>
        )) : <p>공식 일정의 다음 발표일을 재확인하고 있습니다.</p>}
      </section>

      <footer className="archive-note">
        <p>{entry.disclaimer}</p>
        <p>촬영 미리보기 날짜는 현재 보유종목 구조를 보여주기 위한 화면이며, 실제 예약 실행 후 해당 날짜의 공식 자료로 자동 교체됩니다.</p>
      </footer>
    </article>
  );
}

export default function ArchiveApp() {
  const [entries, setEntries] = useState([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [playing, setPlaying] = useState(false);
  const displayEntries = useMemo(() => filmingEntries(entries), [entries]);
  const active = displayEntries.find((entry) => entry.date === selected) || displayEntries[0];

  useEffect(() => {
    api("archive").then((data) => {
      setEntries(data.entries);
      const latest = data.entries[0]?.date;
      setSelected(latest && latest <= "2026-09-25" ? "2026-09-25" : latest || "");
    }).catch((reason) => setError(reason.message));
  }, []);

  useEffect(() => {
    if (!playing) return undefined;
    let frame;
    let previous = performance.now();
    const move = (now) => {
      if (now - previous > 20) {
        window.scrollBy(0, 1);
        previous = now;
      }
      if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4) {
        setPlaying(false);
        return;
      }
      frame = requestAnimationFrame(move);
    };
    frame = requestAnimationFrame(move);
    return () => cancelAnimationFrame(frame);
  }, [playing]);

  const selectDate = (date) => {
    setSelected(date);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (error) return <main className="archive-empty"><h1>일자별 리포트</h1><p>{error}</p></main>;
  if (!active) return <main className="archive-empty"><h1>일자별 리포트</h1><p>오늘의 리포트를 준비하고 있습니다.</p></main>;

  return (
    <div className="archive-site">
      <header className="archive-header">
        <a className="archive-logo" href="/archive">내 투자 브리핑</a>
        <nav><a className="active" href="#reports">일자별 리포트</a><a href="#stocks">보유 종목</a></nav>
        <div className="archive-actions">
          <span><CalendarDays size={16} /> 매일 오전 8시</span>
          <button onClick={() => setPlaying(!playing)}>{playing ? <Pause size={15} /> : <Play size={15} />}{playing ? "멈춤" : "자동 스크롤"}</button>
        </div>
      </header>
      <main id="reports" className="archive-layout">
        <DateRail entries={displayEntries} selected={active.date} onSelect={selectDate} />
        <Report key={active.date} entry={active} />
      </main>
    </div>
  );
}
