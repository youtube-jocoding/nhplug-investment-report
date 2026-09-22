import { useState, useEffect } from "react";
import {
  ArrowUpRight,
  RefreshCw,
  Download,
  Printer,
  Mail as MailIcon,
} from "lucide-react";
import { api } from "./api";
import { Metrics, Allocation, Holdings, Evidence } from "./ReportSections";
import { Connect, Mail, Guide } from "./Dialogs";
import {
  News,
  StockResearch,
  SectorResearch,
  Monitoring,
} from "./Consultation";
export default function App() {
  const [r, setR] = useState(null),
    [modal, setModal] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [delivery, setDelivery] = useState(null);
  const [loaded, setLoaded] = useState(false), [cached, setCached] = useState(false);
  function updateReport(report) { setR(report); setCached(false); setLoaded(true); }
  async function load() {
    try {
      const result = await api("report"); setR(result.report); setCached(result.cached); setLoaded(true);
      setDelivery(await api("delivery"));
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);
  if (!r)
    return (
      <main>
        <h1>포트폴리오 리포트</h1>
        <p role="status">{error || (loaded ? '실제 계좌를 연결하면 보유 종목 분석을 시작합니다.' : "리포트를 불러오는 중입니다…")}</p>
        {loaded && <section className="panel empty-connect"><h2>내 계좌부터 연결하세요.</h2><p>브랜드와 API 키를 검증한 뒤 계좌·시장을 선택합니다.</p>
          <button className="primary" onClick={() => setModal('connect')}>PLUG 연결 시작</button>
          <button onClick={async () => {try {updateReport((await api('demo', {})).report);} catch(e) {setError(e.message);}}}>가상 예시 따로 보기</button>
        </section>}
        {modal === 'connect' && <Connect onReport={updateReport} onClose={() => setModal('')} />}
        {error && <button onClick={load}>다시 시도</button>}
      </main>
    );
  const c = r.consultation;
  return (
    <>
      <header>
        <div className="header-inner">
          <a className="brand" href="#">
            포트폴리오 리포트<span className="brand-dot">.</span>
          </a>
          <nav aria-label="주 메뉴">
            <a href="#stocks">기업 분석</a>
            <a href="#news">최신 뉴스</a>
            <button onClick={() => setModal("guide")}>시작 프롬프트</button>
          </nav>
          <span className="mode">
            {r.snapshot.mode === "demo"
              ? "가상 예시"
              : r.snapshot.mode === "mock"
                ? "모의계좌"
                : "실제 계좌"}
          </span>
          <button disabled={!r.research_status.final_ready} className="mail-button" onClick={() => setModal("mail")}>
            <MailIcon size={15} /> 뉴스레터 미리보기
          </button>
        </div>
      </header>
      <main>
        <div className="intro">
          <p className="eyebrow">YOUR PORTFOLIO, EXPLAINED.</p>
          <h1>숫자를 넘어, 기업의 다음을 읽다.</h1>
          <p className="subtitle">
            보유 종목의 뉴스와 재무제표를 연결한 포트폴리오 브리핑
          </p>
          <p className="meta">
            {r.snapshot.account_label} · 잔고 조회{" "}
            {new Date(r.snapshot.fetched_at).toLocaleString("ko-KR", {
              timeZone: "Asia/Seoul",
            })}{" "}
            KST
            <br />
            기업 자료 확인 {c.as_of || "조사 대기"} · {r.snapshot.scope}
          </p>
        </div>
        {r.snapshot.mode === 'demo' && <p className="notice demo-banner">가상 예시 · 표시된 보유 금액과 손익은 실제 계좌가 아닙니다.</p>}
        {cached && <p className="notice">이전에 저장한 잔고입니다. 현재 잔고는 아래 ‘잔고 새로고침’으로 확인하세요.</p>}
        {!r.research_status.final_ready && <p className="notice">{r.research_status.notice || '자료 조사 대기'} · 검증 완료 {r.research_status.verified}/{r.research_status.total}종목. 조사가 끝나면 뉴스레터와 최종 리포트를 열 수 있습니다.</p>}
        <Metrics r={r} />
        <div className="primary-grid">
          <section className="coaching">
            <p className="memo-label">핵심 진단</p>
            <h2>{c.headline}</h2>
            <p className="lead">{c.summary}</p>
            <div className="brief-bottom">
              <span>
                분석 {c.coverage}/{c.count}개 종목
              </span>
              <a href="#stocks">기업 분석 읽기 ↗</a>
            </div>
          </section>
          <Allocation r={r} />
        </div>
        {c.stale && (
          <p className="notice">
            리서치 확인일은 {c.as_of || "미확인"}입니다. 잔고 새로고침과 기업
            자료 재조사는 별도로 진행합니다.
          </p>
        )}
        <News r={r} />
        <StockResearch key={r.snapshot.fetched_at} r={r} />
        <SectorResearch r={r} />
        <Monitoring r={r} />
        <Holdings r={r} />
        <section className="panel report-library">
          <div>
            <span className="eyebrow">READ & KEEP</span>
            <h2>오늘의 리포트를 편하게 읽으세요.</h2>
            <p>뉴스레터는 핵심만, 상세 리포트는 재무표와 조건별 전망까지.</p>
          </div>
          <div>
            <button disabled={!r.research_status.final_ready} onClick={() => setModal("mail")}>뉴스레터 보기</button>
            <a
              className="button"
              href={r.research_status.final_ready ? "/api/export/html" : undefined}
              aria-disabled={!r.research_status.final_ready}
              target="_blank"
              rel="noreferrer"
            >
              상세 리포트 <ArrowUpRight size={15} />
            </a>
            {delivery?.gmail_url && (
              <a
                className="button"
                href={delivery.gmail_url}
                target="_blank"
                rel="noreferrer"
              >
                발송한 Gmail 열기 ↗
              </a>
            )}
          </div>
        </section>
        <Evidence r={r} />
        <footer className="toolbar">
          {r.snapshot.mode !== "demo" && (
            <button
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  updateReport((await api("refresh", {})).report);
                  setError("");
                } catch (e) {
                  setError(e.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <RefreshCw size={15} />
              {busy ? "조회 중…" : "잔고 새로고침"}
            </button>
          )}
          <button onClick={() => setModal("connect")}>
            PLUG 연결 <ArrowUpRight size={15} />
          </button>
          <a className="button" href={r.research_status.final_ready ? "/api/export/md" : undefined} aria-disabled={!r.research_status.final_ready}>
            <Download size={15} />
            분석 메모
          </a>
          <button onClick={() => window.print()}>
            <Printer size={15} />
            인쇄 / PDF
          </button>
        </footer>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </main>
      {modal === "connect" && (
        <Connect onReport={updateReport} onClose={() => setModal("")} />
      )}{" "}
      {modal === "mail" && <Mail onClose={() => setModal("")} />}{" "}
      {modal === "guide" && <Guide onClose={() => setModal("")} />}
    </>
  );
}
